"""三层缓存：API 响应 / RSS 条目 / 页面快照。JSON 文件实现，无外部依赖。

与现有 core/storage.py 风格保持一致（read_json / write_json）。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class CacheStore:
    def __init__(self, root: Path, default_ttl: int = 900) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl

    @staticmethod
    def make_key(layer: str, *parts: str) -> str:
        raw = layer + "|" + "|".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def get(self, key: str) -> Any | None:
        path = self.root / f"{key}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if time.time() - data.get("stored_at", 0) > data.get("ttl", self.default_ttl):
            return None
        return data.get("payload")

    def get_with_meta(self, key: str) -> tuple[Any | None, dict[str, Any]]:
        path = self.root / f"{key}.json"
        if not path.exists():
            return None, {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None, {}
        if time.time() - data.get("stored_at", 0) > data.get("ttl", self.default_ttl):
            return None, {}
        return data.get("payload"), data.get("meta", {})

    def put(self, key: str, payload: Any, ttl: int | None = None,
            meta: dict[str, Any] | None = None) -> None:
        path = self.root / f"{key}.json"
        path.write_text(
            json.dumps(
                {
                    "stored_at": time.time(),
                    "ttl": ttl if ttl is not None else self.default_ttl,
                    "meta": meta or {},
                    "payload": payload,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def stats(self) -> dict[str, int]:
        files = list(self.root.glob("*.json"))
        valid = sum(1 for f in files if self.get(f.stem) is not None)
        return {"entries": len(files), "valid": valid, "expired": len(files) - valid}
