"""HMAC-signed owner approvals with replay protection.

No secret is stored in the repository. In production set
CLOUD_OS_APPROVAL_SECRET. When absent an ephemeral per-process secret is used,
so approvals intentionally do not survive a restart.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from typing import Any


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class ReplayStore:
    """Thread-safe in-memory nonce store (single process)."""

    def __init__(self) -> None:
        self._used: set[str] = set()
        self._lock = threading.Lock()

    def consume(self, nonce: str) -> bool:
        with self._lock:
            if nonce in self._used:
                return False
            self._used.add(nonce)
            return True

    def reset(self) -> None:
        with self._lock:
            self._used.clear()


class ApprovalGate:
    def __init__(
        self,
        secret: str | None = None,
        *,
        ttl_seconds: int = 900,
        replay_store: ReplayStore | None = None,
    ) -> None:
        env_secret = os.getenv("CLOUD_OS_APPROVAL_SECRET")
        self.secret = secret or env_secret or secrets.token_hex(32)
        self.ephemeral = not (secret or env_secret)
        self.ttl_seconds = ttl_seconds
        self.replay = replay_store or ReplayStore()

    def issue(
        self,
        action: str,
        project: str,
        decision: str,
        approver: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        if decision not in {"approve", "reject", "revise"}:
            raise ValueError("decision must be approve, reject, or revise")
        now = int(time.time())
        payload = {
            "action": action,
            "project": project,
            "decision": decision,
            "approver": approver,
            "iat": now,
            "exp": now + self.ttl_seconds,
            "nonce": secrets.token_hex(16),
            "metadata": metadata or {},
        }
        encoded = _b64e(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
        signature = hmac.new(self.secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def verify(
        self,
        token: str,
        *,
        action: str | None = None,
        project: str | None = None,
        consume: bool = True,
    ) -> dict[str, Any] | None:
        try:
            encoded, signature = token.split(".", 1)
            expected = hmac.new(self.secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return None
            payload = json.loads(_b64d(encoded).decode("utf-8"))
            if int(payload.get("exp", 0)) < int(time.time()):
                return None
            if action and payload.get("action") != action:
                return None
            if project and payload.get("project") != project:
                return None
            nonce = str(payload.get("nonce", ""))
            if not nonce:
                return None
            if consume and not self.replay.consume(nonce):
                return None
            return payload
        except Exception:
            return None


def requires_human_approval(risk: str, amount: float, threshold: float = 100000.0) -> bool:
    """v12 safety boundary: high risk or amount >= threshold needs owner approval."""
    return str(risk).lower() in {"high", "medium"} or amount >= threshold
