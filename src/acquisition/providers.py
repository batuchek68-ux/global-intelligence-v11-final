"""数据源 Provider：GDELT 官方 API（首选） + RSS（次选）。

HTTP 通过注入的 fetcher 完成，便于测试与复用现有 requests。
fetcher(url, headers, params) -> (status, body, headers)
"""
from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import urlencode

from .models import RawItem, SourceTier

Fetcher = Callable[[str, dict[str, str], dict[str, str]], tuple[int, str, dict[str, str]]]


def _parse_datetime(value: str) -> datetime | None:
    """兼容 RSS 的 RFC 2822 与 Atom 的 ISO 8601 时间。"""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        pass
    iso = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class GdeltProvider:
    """GDELT DOC 2.0：免费无 key，硬限制 1 请求/5 秒。

    重试预算必须可控：默认 8 次线性退避会累计 330 秒，足以拖垮 API 路径。
    这里把重试上限与退避参数下沉到实例，由 config/sources.json 注入。
    """

    ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
    MAX_RECORDS = 75
    INTERVAL = 5.0
    DEFAULT_MAX_RETRIES = 2
    DEFAULT_BACKOFF_BASE = 2.0
    DEFAULT_BACKOFF_CAP = 8.0

    def __init__(self, fetcher: Fetcher, acquire: Callable[[str, float | None], float],
                 sleep_fn: Callable[[float], None] | None = None,
                 max_retries: int | None = None,
                 backoff_base: float | None = None,
                 backoff_cap: float | None = None):
        self.fetch = fetcher
        self.acquire = acquire
        self._sleep = sleep_fn or time.sleep
        self.max_retries = max(1, int(max_retries or self.DEFAULT_MAX_RETRIES))
        self.backoff_base = max(
            0.0,
            float(backoff_base if backoff_base is not None else self.DEFAULT_BACKOFF_BASE),
        )
        self.backoff_cap = max(
            self.backoff_base,
            float(backoff_cap if backoff_cap is not None else self.DEFAULT_BACKOFF_CAP),
        )

    def _backoff(self, attempt: int) -> None:
        """指数退避：base * 2^attempt，封顶 backoff_cap。"""
        delay = min(self.backoff_base * (2 ** attempt), self.backoff_cap)
        if delay > 0:
            self._sleep(delay)

    def search(self, query: str, timespan: str = "24h", language: str = "english",
               retries: int | None = None) -> list[RawItem]:
        """retries=None 时使用实例上限；显式传值仅用于测试/验收覆盖。"""
        attempts = self.max_retries if retries is None else max(1, int(retries))
        params = {
            "query": f"{query} sourcelang:{language}",
            "mode": "artlist",
            "format": "json",
            "maxrecords": str(self.MAX_RECORDS),
            "timespan": timespan,
            "sort": "datedesc",
        }
        for attempt in range(attempts):
            self.acquire("gdelt", self.INTERVAL)
            try:
                status, body, headers = self.fetch(self.ENDPOINT, {}, params)
            except Exception:
                self._backoff(attempt)
                continue

            # GDELT 限流时可能返回纯文本而非 429 —— 必须防裸 json.loads
            if status == 429 or not body.lstrip().startswith("{"):
                self._backoff(attempt)
                continue
            if status != 200:
                self._backoff(attempt)
                continue
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self._backoff(attempt)
                continue
            return [self._to_item(a) for a in payload.get("articles", [])]
        raise RuntimeError(f"GDELT 连续限流，已退避 {attempts} 次")

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

    # 修饰词/连接词不参与匹配，否则长模板查询会被整串子串匹配判为 0 命中。
    STOPWORDS = frozenset({
        "official", "government", "project", "owner", "developer", "tender",
        "procurement", "epc", "contractor", "customs", "hs", "code", "tariff",
        "import", "documents", "investment", "promotion", "investor",
        "feasibility", "study", "eia", "ministry", "akimat", "youtube",
        "tiktok", "douyin", "telegram", "forum", "public", "attention",
        "the", "and", "for", "with", "from", "of",
    })

    def __init__(self, fetcher: Fetcher, acquire: Callable[[str, float | None], float],
                 feeds: list[dict[str, Any]],
                 max_workers: int = 4,
                 fetch_timeout: float | None = None):
        self.fetch = fetcher
        self.acquire = acquire
        self.feeds = feeds
        self.max_workers = max(1, int(max_workers or 1))
        self.fetch_timeout = fetch_timeout
        try:
            import inspect
            self._accepts_timeout = "timeout" in inspect.signature(fetcher).parameters
        except (TypeError, ValueError):
            self._accepts_timeout = False

    def search(self, query: str = "", source_ids: list[str] | None = None) -> list[RawItem]:
        targets = [f for f in self.feeds
                   if f.get("enabled", True) and (not source_ids or f["id"] in source_ids)]

        def fetch_feed(feed: dict[str, Any]) -> list[RawItem]:
            self.acquire(f"rss:{feed['id']}", None)
            try:
                # 生产 fetcher 接受 timeout 关键字；测试用三参数 fetcher 时保持兼容。
                # 用签名探测而不是 try/except TypeError，避免回调内部 false-positive。
                if self.fetch_timeout is not None and self._accepts_timeout:
                    status, body, _ = self.fetch(feed["url"], {}, {},
                                                 timeout=self.fetch_timeout)
                else:
                    status, body, _ = self.fetch(feed["url"], {}, {})
            except Exception:
                return []
            return self._parse(body, feed) if status == 200 else []

        if len(targets) <= 1:
            batches = [fetch_feed(f) for f in targets]
        else:
            # 并发抓取：代理阻断的源即使各卡 10s，总耗时也只是最慢的一个。
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(
                max_workers=min(self.max_workers, len(targets)),
                thread_name_prefix="gi-rss",
            ) as executor:
                batches = list(executor.map(fetch_feed, targets))
        items: list[RawItem] = [i for batch in batches for i in batch]
        if query:
            terms = self._query_terms(query)
            # 关键词 OR 命中：只要标题/摘要包含任一实词即召回。
            # 空 terms（全是停用词）时不置空结果，避免误杀。
            if terms:
                items = [
                    i for i in items
                    if any(t in (i.title + " " + i.summary).lower() for t in terms)
                ]
        return items

    @classmethod
    def _query_terms(cls, query: str) -> list[str]:
        """从查询中抽取参与匹配的实词：去引号/标点、去停用词、保留 CJK。"""
        import re
        tokens = re.findall(r"[\w\u4e00-\u9fff]+", query.lower())
        return [t for t in tokens if len(t) > 1 and t not in cls.STOPWORDS]

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
            published = _parse_datetime(pub)
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
