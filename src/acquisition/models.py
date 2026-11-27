"""统一数据模型：所有采集层返回同一结构，供 Judge / 知识图谱消费。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from urllib.parse import urlsplit


class SourceTier(str, Enum):
    OFFICIAL_API = "official_api"
    RSS = "rss"
    LEGACY = "legacy"


class RobotsDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    UNAVAILABLE = "unavailable"   # 4xx: 无规则，允许但告警
    UNREACHABLE = "unreachable"   # 5xx/超时: 完全禁止


@dataclass
class RobotsResult:
    decision: RobotsDecision
    crawl_delay: float | None = None
    matched_rule: str = ""
    cached: bool = False
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RawItem:
    url: str
    title: str
    summary: str = ""
    published_at: datetime | None = None
    source_id: str = ""
    source_tier: SourceTier = SourceTier.RSS
    domain: str = ""
    language: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.url = self.url.strip()
        if not self.url.startswith(("http://", "https://")):
            raise ValueError(f"非法 URL: {self.url}")
        if not self.domain:
            self.domain = urlsplit(self.url).netloc.lower()

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "summary": self.summary,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "source_id": self.source_id,
            "source_tier": self.source_tier.value,
            "domain": self.domain,
            "language": self.language,
            "extra": self.extra,
        }


@dataclass
class ProvenanceRecord:
    source_tier: SourceTier
    fetch_url: str
    robots_decision: RobotsDecision
    fetched_at: datetime
    etag: str | None = None
    cache_key: str | None = None
    fallback_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_tier": self.source_tier.value,
            "fetch_url": self.fetch_url,
            "robots_decision": self.robots_decision.value,
            "fetched_at": self.fetched_at.isoformat(),
            "etag": self.etag,
            "cache_key": self.cache_key,
            "fallback_reason": self.fallback_reason,
        }


@dataclass
class EnrichedItem:
    item: RawItem
    provenance: ProvenanceRecord

    def to_dict(self) -> dict[str, Any]:
        return {"item": self.item.to_dict(), "provenance": self.provenance.to_dict()}


class FallbackExhausted(RuntimeError):
    """所有合规数据源均无结果。"""
