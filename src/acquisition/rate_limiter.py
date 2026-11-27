"""分层限流：全局桶 + 每域名最小间隔。无外部依赖。"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    last_call: float = 0.0
    interval: float = 1.0
    lock: threading.Lock = field(default_factory=threading.Lock)


class RateLimiter:
    def __init__(
        self,
        default_interval: float = 2.0,
        domain_intervals: dict[str, float] | None = None,
        global_interval: float = 0.0,
    ) -> None:
        self.default_interval = default_interval
        self.domain_intervals = domain_intervals or {}
        self.global_bucket = _Bucket(interval=global_interval)
        self._domains: dict[str, _Bucket] = {}
        self._guard = threading.Lock()

    def _bucket(self, key: str) -> _Bucket:
        with self._guard:
            if key not in self._domains:
                self._domains[key] = _Bucket(interval=self.domain_intervals.get(key, self.default_interval))
            return self._domains[key]

    def acquire(self, key: str, interval: float | None = None) -> float:
        """阻塞直到可请求；返回实际等待秒数。"""
        waited = 0.0
        if self.global_bucket.interval > 0:
            waited += self._wait(self.global_bucket, None)
        bucket = self._bucket(key)
        waited += self._wait(bucket, interval)
        return waited

    @staticmethod
    def _wait(bucket: _Bucket, interval: float | None) -> float:
        with bucket.lock:
            gap = interval if interval is not None else bucket.interval
            now = time.monotonic()
            remaining = gap - (now - bucket.last_call)
            if remaining > 0:
                time.sleep(remaining)
            bucket.last_call = time.monotonic()
            return max(remaining, 0.0)
