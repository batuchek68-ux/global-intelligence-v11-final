"""Polling bridge for external intelligence sources.

Each new item becomes a durable event, so downstream agents can react without
waiting for the next fixed cron tick. No source data is modified.
"""
from __future__ import annotations

import json
import os
from typing import Any

import requests


def configured_sources() -> list[dict[str, str]]:
    raw = os.getenv("CLOUD_OS_RSS_SOURCES") or "[]"
    try:
        data = json.loads(raw)
        return [{"name": str(x.get("name") or "source"), "url": str(x.get("url") or "")} for x in data if x.get("url")]
    except Exception:
        return []


def fetch_rss(url: str, timeout: int = 20) -> list[dict[str, str]]:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "v12-intel/1.0"})
    response.raise_for_status()
    try:
        import feedparser
        parsed = feedparser.parse(response.content)
    except Exception:
        return []
    items = []
    for entry in getattr(parsed, "entries", [])[:20]:
        items.append({
            "title": str(getattr(entry, "title", "")),
            "link": str(getattr(entry, "link", "")),
            "published": str(getattr(entry, "published", "")),
        })
    return items


def poll_sources(sources: list[dict[str, str]] | None = None) -> dict[str, Any]:
    from backend.services.event_bus import publish
    sources = sources if sources is not None else configured_sources()
    published = 0
    details = []
    for source in sources:
        try:
            items = fetch_rss(source["url"])
        except Exception as exc:
            details.append({"source": source.get("name"), "error": str(exc), "items": 0})
            continue
        for item in items:
            publish("intel.source_updated", {
                "source": source.get("name"),
                "url": source.get("url"),
                **item,
            })
            published += 1
        details.append({"source": source.get("name"), "items": len(items)})
    return {"ok": True, "published": published, "details": details}
