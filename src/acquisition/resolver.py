"""SourceResolver —— API → RSS → Legacy 降级链 + robots 硬闸 + 溯源。"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Callable

from .models import (
    EnrichedItem, FallbackExhausted, ProvenanceRecord,
    RawItem, RobotsDecision, SourceTier,
)
from .robots_gate import RobotsGate


class SourceResolver:
    def __init__(
        self,
        gate: RobotsGate,
        api: Any,          # GdeltProvider
        rss: Any,          # RssProvider
        legacy: Callable[[str], list[RawItem]] | None,
        cache: Any | None = None,
        strategy: str = "hybrid",
    ) -> None:
        self.gate = gate
        self.api = api
        self.rss = rss
        self.legacy = legacy
        self.cache = cache
        self.strategy = strategy
        self.fallback_log: list[dict[str, str]] = []

    def resolve(self, intent: str, timespan: str = "24h",
                language: str = "english",
                rss_query: str | None = None) -> list[EnrichedItem]:
        """rss_query 可为 RSS 层单独指定短查询；不传则沿用 intent。

        API 层（GDELT）支持带限定词的检索语法，RSS 层只做关键词匹配，
        两者对查询串的要求不同，因此需要分开传入。
        """
        chain: list[tuple[SourceTier, Callable[[], list[RawItem]]]] = [
            (SourceTier.OFFICIAL_API, lambda: self.api.search(intent, timespan, language)),
            (SourceTier.RSS, lambda: self.rss.search(rss_query or intent)),
        ]
        if self.legacy and self.strategy != "compliance_first":
            chain.append((SourceTier.LEGACY, lambda: self.legacy(intent)))

        results: list[EnrichedItem] = []
        for tier, fetch in chain:
            try:
                raw_items = fetch()
            except Exception as exc:
                self._fallback(tier, f"error:{type(exc).__name__}:{exc}")
                continue
            if not raw_items:
                self._fallback(tier, "empty-result")
                continue
            for item in raw_items:
                robots = self.gate.check(item.url)
                if robots.decision in (RobotsDecision.DENY, RobotsDecision.UNREACHABLE):
                    self._fallback(tier, f"robots:{robots.decision.value}:{item.url}")
                    continue
                results.append(EnrichedItem(
                    item=item,
                    provenance=ProvenanceRecord(
                        source_tier=tier,
                        fetch_url=item.url,
                        robots_decision=robots.decision,
                        fetched_at=datetime.now(timezone.utc),
                        fallback_reason=self.fallback_log[-1]["reason"] if self.fallback_log else None,
                    ),
                ))
            if results:
                return self._dedup(results)
        if self.strategy == "compliance_first" and not results:
            raise FallbackExhausted(f"所有合规数据源均无结果: {intent}")
        return self._dedup(results)

    def _fallback(self, tier: SourceTier, reason: str) -> None:
        self.fallback_log.append({"tier": tier.value, "reason": reason})
        # 生产环境接入 metrics: fallback_total{from_tier,reason}

    @staticmethod
    def _dedup(items: list[EnrichedItem]) -> list[EnrichedItem]:
        seen_url: set[str] = set()
        seen_title: set[str] = set()
        out: list[EnrichedItem] = []
        for e in sorted(items, key=lambda x: x.item.published_at or datetime.min.replace(tzinfo=timezone.utc)):
            u = hashlib.sha256(e.item.url.encode()).hexdigest()
            t = hashlib.sha256(" ".join(e.item.title.lower().split()).encode()).hexdigest()
            if u in seen_url or t in seen_title:
                continue
            seen_url.add(u)
            seen_title.add(t)
            out.append(e)
        return out
