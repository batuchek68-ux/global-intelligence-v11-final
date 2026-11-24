"""Local knowledge layer: chunk, embed, index and retrieve.

Sources are read-only. The vector index is persisted under backend/memory/chroma
(or KNOWLEDGE_CHROMA_DIR). All processing stays on this machine.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = BACKEND_ROOT / "memory" / "chroma"
VAULT = Path("F:/Documents/Obsidian Vault/obsidian-codex/00-输入池")
DEFAULT_SOURCES = {
    "wiki": Path("F:/Documents/Obsidian Vault/wiki"),
    "wechat_favorites": VAULT / "wechat/收藏",
    "wechat_files": VAULT / "wechat/文件",
    "wechat_chat": VAULT / "wechat/聊天记录",
    "workbuddy": VAULT / "workbuddy",
    "ima": VAULT / "ima-知识库",
    "github": VAULT / "github",
}

COLLECTION = "intelligence_knowledge"
CHUNK_SIZE = 2500
CHUNK_OVERLAP = 100
MAX_DOCS_PER_SOURCE = int(os.getenv("KNOWLEDGE_MAX_DOCS", "200"))


def _sources() -> dict[str, Path]:
    override = os.getenv("KNOWLEDGE_SOURCES")
    if override:
        try:
            return {k: Path(v) for k, v in json.loads(override).items()}
        except Exception:
            pass
    return dict(DEFAULT_SOURCES)


def _db_path() -> Path:
    return Path(os.getenv("KNOWLEDGE_CHROMA_DIR") or str(DEFAULT_DB))


def _embedding_function():
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    return DefaultEmbeddingFunction()


def _client():
    import chromadb
    path = _db_path()
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def _collection(reset: bool = False):
    client = _client()
    if reset:
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
    return client.get_or_create_collection(
        name=COLLECTION,
        embedding_function=_embedding_function(),
        metadata={"hnsw:space": "cosine"},
    )


def _clean(text: str) -> str:
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"!\[\[[^\]]+\]\]", "", text)
    text = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", r"\2\1", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _chunks(text: str) -> list[str]:
    if len(text) <= CHUNK_SIZE:
        return [text] if text else []
    out = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        out.append(text[start:end])
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP
    return out


def build_index(reset: bool = True, limit_per_source: int | None = None) -> dict[str, Any]:
    limit_per_source = limit_per_source if limit_per_source is not None else MAX_DOCS_PER_SOURCE
    collection = _collection(reset=reset)
    print(f"[knowledge] building index at {_db_path()} (limit/source={limit_per_source}, chunk={CHUNK_SIZE})", flush=True)
    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []
    per_source: dict[str, int] = {}
    for name, root in _sources().items():
        if not root.exists():
            continue
        files = sorted(root.rglob("*.md"))
        if limit_per_source:
            files = files[:limit_per_source]
        count = 0
        for path in files:
            try:
                raw = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, chunk in enumerate(_chunks(_clean(raw))):
                ids.append(f"{name}::{path.as_posix()}::{i}")
                documents.append(chunk)
                metadatas.append({
                    "source": name,
                    "path": path.as_posix(),
                    "title": path.stem,
                    "chunk": i,
                })
                count += 1
        per_source[name] = count
        print(f"[knowledge] {name}: {len(files)} files -> {count} chunks", flush=True)
    if ids:
        print(f"[knowledge] embedding {len(ids)} chunks...", flush=True)
        for i in range(0, len(ids), 200):
            collection.add(ids=ids[i:i + 200], documents=documents[i:i + 200], metadatas=metadatas[i:i + 200])
    return {"ok": True, "chunks": len(ids), "per_source": per_source, "collection": COLLECTION}


def query(text: str, n: int = 5) -> dict[str, Any]:
    collection = _collection(reset=False)
    if collection.count() == 0:
        return {"ok": False, "reason": "empty index", "results": []}
    result = collection.query(query_texts=[text], n_results=min(n, collection.count()))
    items = []
    for doc, meta, dist in zip(result["documents"][0], result["metadatas"][0], result["distances"][0]):
        items.append({"text": doc, "metadata": meta, "distance": dist})
    return {"ok": True, "results": items}


def stats() -> dict[str, Any]:
    collection = _collection(reset=False)
    return {"ok": True, "count": collection.count(), "collection": COLLECTION, "path": str(_db_path())}


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Simple retrieval eval: each case has `query` and `expect_keywords`."""
    hits = 0
    details = []
    for case in cases:
        res = query(str(case.get("query", "")), n=int(case.get("n", 5)))
        blob = " ".join(r["text"] for r in res.get("results", [])).lower()
        keywords = [str(k).lower() for k in case.get("expect_keywords", [])]
        found = [k for k in keywords if k in blob]
        ok = bool(keywords) and len(found) >= max(1, len(keywords) // 2)
        hits += int(ok)
        details.append({"query": case.get("query"), "found": found, "ok": ok})
    return {"ok": True, "total": len(cases), "hits": hits, "accuracy": hits / len(cases) if cases else 0.0, "details": details}
