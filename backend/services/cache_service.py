"""Small TTL cache with optional Redis backend.

Without REDIS_URL this is an in-process dict with expiry, adequate for a single
worker. With REDIS_URL set and the redis package installed, it uses Redis.
"""
from __future__ import annotations

import os
import time
from typing import Any


class TTLCache:
    def __init__(self, default_ttl: int = 300) -> None:
        self.default_ttl = default_ttl
        self._data: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Any | None:
        item = self._data.get(key)
        if not item:
            return None
        value, expires = item
        if expires < time.time():
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        effective = self.default_ttl if ttl is None else ttl
        self._data[key] = (value, time.time() + effective)

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def clear(self) -> None:
        self._data.clear()

    def size(self) -> int:
        return len(self._data)


_LOCAL = TTLCache()


def get(key: str) -> Any | None:
    url = os.getenv("REDIS_URL")
    if url:
        try:
            import redis
            client = redis.from_url(url)
            value = client.get(key)
            return value.decode("utf-8") if isinstance(value, bytes) else value
        except Exception:
            return _LOCAL.get(key)
    return _LOCAL.get(key)


def set(key: str, value: Any, ttl: int = 300) -> None:
    url = os.getenv("REDIS_URL")
    if url:
        try:
            import redis
            client = redis.from_url(url)
            client.setex(key, ttl, str(value))
            return
        except Exception:
            pass
    _LOCAL.set(key, value, ttl)


def delete(key: str) -> None:
    url = os.getenv("REDIS_URL")
    if url:
        try:
            import redis
            redis.from_url(url).delete(key)
            return
        except Exception:
            pass
    _LOCAL.delete(key)


def clear() -> None:
    _LOCAL.clear()


def health() -> dict[str, Any]:
    return {"ok": True, "backend": "redis" if os.getenv("REDIS_URL") else "memory", "size": _LOCAL.size()}
