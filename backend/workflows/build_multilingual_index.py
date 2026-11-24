#!/usr/bin/env python3
"""Detached worker: rebuild the multilingual vector index.

Run via Start-Process so it survives OpenCode service restarts.
Writes progress to backend/memory/chroma-ml/build.log.
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
for p in (ROOT, BACKEND):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("KNOWLEDGE_EMBED_MODEL", "multilingual")
os.environ.setdefault("KNOWLEDGE_CHROMA_DIR", str(BACKEND / "memory" / "chroma-ml"))
os.environ.setdefault("KNOWLEDGE_MAX_DOCS", "1000")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

LOG = BACKEND / "memory" / "chroma-ml" / "build.log"


def log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def main() -> None:
    log("START multilingual index build")
    try:
        from backend.services.knowledge_ingest_service import build_index, stats
        t = time.time()
        result = build_index(reset=True)
        log(f"DONE chunks={result['chunks']} seconds={round(time.time()-t,1)} stats={stats()}")
    except Exception:
        log("ERROR\n" + traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
