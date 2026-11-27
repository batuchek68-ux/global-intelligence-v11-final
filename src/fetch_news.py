"""src/fetch_news.py 的合规改造版 —— 保持原有调用方式与输出路径。

原版：硬编码 CNN/BBC/Al Jazeera 三个 RSS，feedparser 直抓，无 robots/限流/缓存/溯源。
改造版：GDELT 官方 API 优先 → RSS 次选 → robots 硬闸 → 溯源落盘。

向后兼容：仍导出 fetch_news()，仍写 data/raw_news.json，
原字段 title/summary/source 保留，新增 _provenance 字段。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

try:  # 直接运行 src/fetch_news.py 时 sys.path[0] 是 src/
    from acquisition import (
        CacheStore, GdeltProvider, RateLimiter, RobotsGate,
        RssProvider, SourceResolver,
    )
except ModuleNotFoundError:  # 从仓库根 import src.fetch_news 时
    from src.acquisition import (
        CacheStore, GdeltProvider, RateLimiter, RobotsGate,
        RssProvider, SourceResolver,
    )

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "sources.json"


def _load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _http_fetch(url: str, headers: dict[str, str], params: dict[str, str]) -> tuple[int, str, dict[str, str]]:
    """使用仓库 requirements 中已有的 requests；失败时向上抛，由各层自行退避。"""
    import requests  # 延迟导入，便于无依赖环境下测试其他模块
    resp = requests.get(url, headers=headers, params=params or None, timeout=30)
    return resp.status_code, resp.text, dict(resp.headers)


def build_resolver(config: dict[str, Any], cache_root: Path | None = None) -> SourceResolver:
    limits = config.get("rate_limits", {})
    limiter = RateLimiter(
        default_interval=limits.get("default_interval_seconds", 2.0),
        domain_intervals=limits.get("domains", {}),
        global_interval=limits.get("global_interval_seconds", 0.0),
    )
    # RobotsGate 的 fetcher 签名是 (url, headers)，provider 的是 (url, headers, params)。
    # 必须适配，否则 robots 检查会抛 TypeError 被判为 unreachable，导致全部结果被丢弃。
    def _robots_fetch(url: str, headers: dict[str, str]) -> tuple[int, str, dict[str, str]]:
        return _http_fetch(url, headers, {})

    gate = RobotsGate(_robots_fetch, user_agent=config.get("user_agent", ""))
    api = GdeltProvider(_http_fetch, limiter.acquire)
    rss = RssProvider(_http_fetch, limiter.acquire, config.get("feeds", []))
    cache_root = cache_root or Path(config.get("cache", {}).get("root", "data/acquisition_cache"))
    cache = CacheStore(cache_root)
    return SourceResolver(
        gate=gate, api=api, rss=rss, legacy=None, cache=cache,
        strategy=config.get("strategy", "hybrid"),
    )


def fetch_news(query: str = "Kazakhstan port construction investment",
               timespan: str = "24h", out_path: str = "data/raw_news.json") -> list[dict[str, Any]]:
    """兼容原版 fetch_news()，输出同样文件结构。"""
    config = _load_config()
    resolver = build_resolver(config)
    items = resolver.resolve(query, timespan=timespan,
                             language=config.get("gdelt", {}).get("default_language", "english"))
    records: list[dict[str, Any]] = []
    for e in items:
        d = e.item.to_dict()
        records.append({
            "title": d["title"],
            "summary": d["summary"],
            "source": d["source_id"],
            "url": d["url"],
            "published_at": d["published_at"],
            "_provenance": e.provenance.to_dict(),
        })
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    Path(out_path).write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[OK] fetched {len(records)} news (fallbacks={len(resolver.fallback_log)})")
    return records


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "Kazakhstan port construction investment"
    fetch_news(q)
