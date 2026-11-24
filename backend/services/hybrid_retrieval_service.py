"""Hybrid retrieval: vector candidates + lexical re-ranking.

ONNX MiniLM is English-centric; for CJK/mixed queries lexical overlap materially
improves precision. This service re-ranks vector candidates without new deps.
"""
from __future__ import annotations

import re
from typing import Any

from backend.services.knowledge_ingest_service import query as vector_query

_TOKEN_RE = re.compile(r"[a-zA-Z]{3,}|[\u4e00-\u9fff]{2,}")


def _tokens(text: str) -> set[str]:
    raw = _TOKEN_RE.findall(text.lower())
    out: set[str] = set()
    for token in raw:
        if re.match(r"^[a-zA-Z]", token):
            out.add(token)
            if len(token) > 5:
                out.add(token[:4])
        else:
            out.add(token)
            for i in range(len(token) - 1):
                out.add(token[i:i + 2])
    return out


def hybrid_query(text: str, n: int = 5, pool: int = 30) -> dict[str, Any]:
    response = vector_query(text, n=min(pool, 60))
    if not response.get("ok") or not response.get("results"):
        return response
    q_tokens = _tokens(text)
    ranked = []
    for item in response["results"]:
        body = item.get("text") or ""
        meta = item.get("metadata") or {}
        content = f"{body} {meta.get('title', '')}"
        tokens = _tokens(content)
        overlap = len(q_tokens & tokens)
        score = overlap + (0.5 if meta.get("source") in {"wiki", "ima", "github"} else 0)
        ranked.append((score, -float(item.get("distance") or 0), item))
    ranked.sort(key=lambda r: (r[0], r[1]), reverse=True)
    results = [dict(item, lexical_score=score) for score, _, item in ranked[:n]]
    return {"ok": True, "results": results, "hybrid": True}
