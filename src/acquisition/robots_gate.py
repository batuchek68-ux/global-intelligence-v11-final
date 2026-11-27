"""RobotsGate —— RFC 9309 语义的 robots.txt 判定。

关键差异（相对 Python 标准库 robotparser）：
- 自行实现 Allow/Disallow 最长 octet 匹配，等长时 Allow 优先。
- 严格区分 4xx(unavailable -> 允许) 与 5xx/超时(unreachable -> 禁止)。
- 缓存 TTL <= 24h，支持 ETag 条件刷新。
- 无外部依赖，仅用标准库。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from .models import RobotsDecision, RobotsResult

MAX_CACHE_TTL = 24 * 60 * 60
MAX_REDIRECTS = 5
DEFAULT_UA = "global-intelligence-v11-collector/1.0 (+compliance-first)"


@dataclass
class _CacheEntry:
    rules: list[tuple[str, bool]] = field(default_factory=list)  # (path, is_allow)
    crawl_delay: float | None = None
    cached_at: float = 0.0
    etag: str | None = None
    unavailable: bool = False


class RobotsGate:
    def __init__(
        self,
        fetcher: Callable[[str, dict[str, str]], tuple[int, str, dict[str, str]]],
        user_agent: str = DEFAULT_UA,
        cache_ttl: int = MAX_CACHE_TTL,
    ) -> None:
        """fetcher(url, headers) -> (status_code, body, headers)"""
        self._fetch = fetcher
        self.user_agent = user_agent or DEFAULT_UA
        self.cache_ttl = min(cache_ttl, MAX_CACHE_TTL)
        self._cache: dict[str, _CacheEntry] = {}

    def check(self, url: str) -> RobotsResult:
        parts = urlsplit(url)
        host = parts.netloc.lower()
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query

        entry = self._cache.get(host)
        now = time.time()
        if entry is None or now - entry.cached_at >= self.cache_ttl:
            entry = self._fetch_robots(host, entry)
            if entry is None:          # unreachable -> fail closed
                return RobotsResult(
                    decision=RobotsDecision.UNREACHABLE,
                    matched_rule="robots.txt fetch failed (5xx/timeout)",
                )
            self._cache[host] = entry

        if entry.unavailable:
            return RobotsResult(
                decision=RobotsDecision.UNAVAILABLE,
                crawl_delay=entry.crawl_delay,
                matched_rule="robots.txt 4xx -> no rules apply",
                cached=now - entry.cached_at > 0,
            )

        allowed, rule = self._resolve(entry.rules, path)
        return RobotsResult(
            decision=RobotsDecision.ALLOW if allowed else RobotsDecision.DENY,
            crawl_delay=entry.crawl_delay,
            matched_rule=rule,
            cached=now - entry.cached_at > 0,
        )

    def _fetch_robots(self, host: str, old: _CacheEntry | None) -> _CacheEntry | None:
        url = f"https://{host}/robots.txt"
        headers = {"User-Agent": self.user_agent}
        if old and old.etag:
            headers["If-None-Match"] = old.etag
        try:
            status, body, resp_headers = self._fetch(url, headers)
        except Exception:              # 超时/网络错误 -> unreachable
            return old                  # 旧缓存可沿用；无缓存则 fail closed

        if status == 304 and old:
            return _CacheEntry(
                rules=old.rules,
                crawl_delay=old.crawl_delay,
                cached_at=time.time(),
                etag=old.etag,
            )
        if 400 <= status < 500:
            return _CacheEntry(unavailable=True, cached_at=time.time())
        if status >= 500:
            return old
        if status >= 300:
            return old                  # fetcher 应已跟随重定向；未跟随则按失败处理

        rules, delay = self._parse(body)
        return _CacheEntry(
            rules=rules,
            crawl_delay=delay,
            cached_at=time.time(),
            etag=resp_headers.get("etag"),
        )

    def _parse(self, body: str) -> tuple[list[tuple[str, bool]], float | None]:
        """按 UA 组解析；仅取匹配本 UA 的规则组，未匹配则取 * 组。"""
        groups: list[tuple[list[str], list[tuple[str, bool]], float | None]] = []
        current_ua: list[str] = []
        current_rules: list[tuple[str, bool]] = []
        crawl_delay: float | None = None

        for raw in body.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip().lower()
            value = value.strip()

            if key == "user-agent":
                if current_rules:        # 新组开始
                    groups.append((current_ua, current_rules, crawl_delay))
                    current_ua, current_rules, crawl_delay = [], [], None
                current_ua.append(value.lower())
            elif key in ("allow", "disallow"):
                if not current_ua:
                    continue
                if key == "disallow" and not value:
                    continue             # 空 Disallow = 允许全部
                current_rules.append((value, key == "allow"))
            elif key == "crawl-delay":
                try:
                    crawl_delay = float(value)
                except ValueError:
                    pass
            # Sitemap 等"其他记录"不干扰标准记录，也不终止组

        if current_ua or current_rules:
            groups.append((current_ua, current_rules, crawl_delay))

        ua = self.user_agent.lower()
        product = ua.split("/", 1)[0]
        matched = [g for g in groups if any(a == "*" or a in ua or a == product for a in g[0])]
        if not matched:
            matched = [g for g in groups if any(a == "*" for a in g[0])]
        if not matched:
            return [], None

        rules: list[tuple[str, bool]] = []
        delay: float | None = None
        for _, group_rules, group_delay in matched:
            rules.extend(group_rules)
            if group_delay is not None:
                delay = group_delay
        return rules, delay

    @staticmethod
    def _resolve(rules: list[tuple[str, bool]], path: str) -> tuple[bool, str]:
        """最长 octet 匹配；等长 Allow 优先；无匹配默认允许。"""
        if not rules:
            return True, "no rules -> allow"
        best_len = -1
        best_allow = True
        best_rule = ""
        for rule_path, is_allow in rules:
            if not path.startswith(rule_path):
                continue
            if len(rule_path) > best_len or (len(rule_path) == best_len and is_allow and not best_allow):
                best_len = len(rule_path)
                best_allow = is_allow
                best_rule = f"{'Allow' if is_allow else 'Disallow'}: {rule_path}"
        if best_len < 0:
            return True, "no match -> allow"
        return best_allow, best_rule or "implicit allow"


# 保留对标准库的引用仅作接口兼容说明；实际判定由 _resolve 完成。
_ = RobotFileParser
