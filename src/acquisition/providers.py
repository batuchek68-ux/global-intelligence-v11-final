"""数据源 Provider：GDELT 官方 API（首选） + RSS（次选）。

HTTP 通过注入的 fetcher 完成，便于测试与复用现有 requests。
fetcher(url, headers, params) -> (status, body, headers)
"""
from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import urlencode

from .models import RawItem, SourceTier

Fetcher = Callable[[str, dict[str, str], dict[str, str]], tuple[int, str, dict[str, str]]]


class GdeltProvider:
    """GDELT DOC 2.0：免费无 key，硬限制 1 请求/5 秒。"""

    ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
    MAX_RECORDS = 75
    INTERVAL = 5.0

    def __init__(self, fetcher: Fetcher, acquire: Callable[[str, float | None], float],
                 sleep_fn: Callable[[float], None] | None = None):
        self.fetch = fetcher
        self.acquire = acquire
        self._sleep = sleep_fn or time.sleep

    def search(self, query: str, timespan: str = "24h", language: str = "english",
               retries: int = 8) -> list[RawItem]:
        params = {
            "query": f"{query} sourcelang:{language}",
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(self.MAX_RECORDS),
            "timespan": timespan,
            "sort": "datedesc",
        }
        for attempt in range(retries):
            self.acquire("gdelt", self.INTERVAL)
            try:
                status, body, headers = self.fetch(self.ENDPOINT, {}, params)
            except Exception:
                self._sleep(min(10 * (attempt + 1), 60))
                continue

            # GDELT 限流时可能返回纯文本而非 429 —— 必须防裸 json.loads
            if status == 429 or not body.lstrip().startswith("{"):
                self._sleep(min(10 * (attempt + 1), 60))
                continue
            if status != 200:
                self._sleep(min(10 * (attempt + 1), 60))
                continue
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self._sleep(min(10 * (attempt + 1), 60))
                continue
            return [self._to_item(a) for a in payload.get("articles", [])]
        raise RuntimeError("GDELT 连续限流，已退避 8 次")

    @staticmethod
    def _to_item(a: dict[str, Any]) -> RawItem:
        seendate = a.get("seendate") or ""
        published = None
        if len(seendate) >= 15:
            try:
                published = time.strptime(seendate, "%Y%m%d%H%M%S")
                published = __import__("datetime").datetime(*published[:6])
            except ValueError:
                published = None
        return RawItem(
            url=a.get("url", ""),
            title=(a.get("title") or "").strip(),
            summary="",
            published_at=published,
            source_id=a.get("domain") or "gdelt",
            source_tier=SourceTier.OFFICIAL_API,
            domain=a.get("domain") or "",
            language=a.get("language") or "",
            extra={
                "seendate": seendate,
                "tone": a.get("tone"),
                "sourcecountry": a.get("sourcecountry"),
            },
        )


class RssProvider:
    """RSS/Atom：仅取元数据（title/link/summary），不抓正文。"""

    def __init__(self, fetcher: Fetcher, acquire: Callable[[str, float | None], float],
                 feeds: list[dict[str, Any]]):
        self.fetch = fetcher
        self.acquire = acquire
        self.feeds = feeds

    def search(self, query: str = "", source_ids: list[str] | None = None) -> list[RawItem]:
        items: list[RawItem] = []
        targets = [f for f in self.feeds
                   if f.get("enabled", True) and (not source_ids or f["id"] in source_ids)]
        for feed in targets:
            self.acquire(f"rss:{feed['id']}", None)
            try:
                status, body, _ = self.fetch(feed["url"], {}, {})
            except Exception:
                continue
            if status != 200:
                continue
            items.extend(self._parse(body, feed))
        if query:
            q = query.lower()
            items = [i for i in items if q in (i.title + " " + i.summary).lower()]
        return items

    @staticmethod
    def _parse(body: str, feed: dict[str, Any]) -> list[RawItem]:
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return []
        out: list[RawItem] = []
        ns = {"atom": "http://www.w3.org/2005/Atom", "content": "http://purl.org/rss/1.0/modules/content/"}
        entries = root.findall(".//item") or root.findall(".//atom:entry", ns)
        for e in entries:
            def text(*paths: str) -> str:
                for p in paths:
                    node = e.find(p, ns)
                    if node is not None and node.text:
                        return node.text.strip()
                return ""

            url = text("link", "atom:link")
            if not url and e.find("atom:link", ns) is not None:
                url = e.find("atom:link", ns).attrib.get("href", "")
            if not url:
                continue
            title = text("title", "atom:title")
            summary = text("description", "atom:summary", "content:encoded", "atom:content")
            pub = text("pubDate", "published", "atom:published", "atom:updated")
            published = None
            if pub:
                try:
                    published = parsedate_to_datetime(pub)
                except (TypeError, ValueError):
                    published = None
            try:
                out.append(RawItem(
                    url=url, title=title, summary=summary[:500], published_at=published,
                    source_id=feed["id"], source_tier=SourceTier.RSS,
                    language=feed.get("language", ""),
                    extra={"license": feed.get("license", "unknown"), "region": feed.get("region", "")},
                ))
            except ValueError:
                continue
        return out
