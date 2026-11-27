# -*- coding: utf-8 -*-
"""Two-stage retrieval over kb-core (multilingual) with Cross-Encoder reranking.

Fallback: if kb-core absent or reranker unavailable, degrade to lexical-only on
the legacy index so the API never breaks.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = BACKEND_ROOT / "memory" / "kb-core"
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RERANK_MODEL = "BAAI/bge-reranker-base"

_ef = None
_reranker = None
_reranker_tried = False


def _embedding_function():
    global _ef
    if _ef is not None:
        return _ef

    class EF:
        def __init__(self, model):
            self.model = model
        def __call__(self, input):
            texts = [input] if isinstance(input, str) else list(input)
            return self.model.encode(texts, batch_size=64, convert_to_numpy=True).tolist()
        def embed_query(self, input):
            return self(input)
        def embed_documents(self, input):
            return self(input)
        def name(self):
            return "multilingual-minilm"

    from sentence_transformers import SentenceTransformer
    # 优先用本地快照路径，避开 huggingface_hub 的联网校验（offline 下仍会重试 5 次）
    local = Path(os.getenv(
        "CORE_EMBED_LOCAL_PATH",
        "C:/Users/Surface/.cache/huggingface/hub/models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2/snapshots/e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
    ))
    model_id = str(local) if (local / "config.json").exists() else MODEL
    _ef = EF(SentenceTransformer(model_id))
    return _ef


def warmup() -> bool:
    """Preload the embedding model on the main thread at API startup.

    sentence-transformers' first load inside asyncio.to_thread worker can stall;
    doing it here (startup, main thread) makes later offloaded queries fast.
    """
    try:
        _embedding_function()
        return True
    except Exception:
        return False


def _get_reranker():
    global _reranker, _reranker_tried
    if _reranker_tried:
        return _reranker
    _reranker_tried = True
    # 先确认权重文件完整存在，避免 CrossEncoder 反复联网校验导致分钟级卡顿
    try:
        from huggingface_hub import try_to_load_from_cache
        from pathlib import Path
        weight = try_to_load_from_cache(RERANK_MODEL, "pytorch_model.bin")
        if not weight or not Path(weight).exists():
            alt = try_to_load_from_cache(RERANK_MODEL, "model.safetensors")
            if not alt or not Path(alt).exists():
                return None
    except Exception:
        return None
    try:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(RERANK_MODEL)
    except Exception:
        _reranker = None
    return _reranker


def _fallback(text: str, n: int) -> dict[str, Any]:
    from backend.services.hybrid_retrieval_service import hybrid_query
    return hybrid_query(text, n=n)


def retrieve(text: str, n: int = 5, pool: int = 80, min_score: float = 0.30) -> dict[str, Any]:
    """Retrieve from kb-core, rerank, filter by absolute similarity threshold."""
    if not (CORE_DIR / "chroma.sqlite3").exists():
        return _fallback(text, n)
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CORE_DIR))
        col = client.get_collection("kb_core", embedding_function=_embedding_function())
        if col.count() == 0:
            return _fallback(text, n)
        res = col.query(query_texts=[text], n_results=min(pool, col.count()))
        candidates = []
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
            sim = 1.0 - float(dist or 1.0)  # cosine space
            if sim < min_score:
                continue
            candidates.append({
                "text": doc,
                "metadata": meta,
                "distance": dist,
                "similarity": round(sim, 4),
            })
        if not candidates:
            return {"ok": True, "results": [], "note": "no candidate above threshold", "index": "kb_core"}

        reranker = _get_reranker()
        if reranker is not None:
            pairs = [(text, c["text"][:512]) for c in candidates]
            scores = reranker.predict(pairs)
            for c, s in zip(candidates, scores):
                c["rerank_score"] = round(float(s), 4)
            candidates.sort(key=lambda c: c["rerank_score"], reverse=True)
        else:
            candidates.sort(key=lambda c: c["similarity"], reverse=True)
        return {
            "ok": True,
            "results": candidates[:n],
            "index": "kb_core",
            "reranked": reranker is not None,
            "total_candidates": len(candidates),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "fallback": _fallback(text, n)}
