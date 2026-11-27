"""合规优先采集包 —— 用于 global-intelligence-v11-final。

挂载点：
1. src/fetch_news.py        -> 替换硬编码 RSS 抓取
2. backend/core/agents.py   -> EvidencePlannerAgent 接入
3. backend/core/judge.py    -> 读取 provenance 做合规校验
"""
from .models import (
    EnrichedItem, FallbackExhausted, ProvenanceRecord,
    RawItem, RobotsDecision, RobotsResult, SourceTier,
)
from .robots_gate import RobotsGate
from .rate_limiter import RateLimiter
from .cache import CacheStore
from .providers import GdeltProvider, RssProvider
from .resolver import SourceResolver

__all__ = [
    "EnrichedItem", "FallbackExhausted", "ProvenanceRecord", "RawItem",
    "RobotsDecision", "RobotsResult", "SourceTier", "RobotsGate",
    "RateLimiter", "CacheStore", "GdeltProvider", "RssProvider", "SourceResolver",
]
