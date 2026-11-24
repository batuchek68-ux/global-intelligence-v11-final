"""Outbound alert channels with local deduplication.

No alert leaves the machine unless CLOUD_OS_ALERT_WEBHOOK is configured.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from backend.services.state_repository import list_state, save_state

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALERT_LOG = BACKEND_ROOT / "memory" / "alerts.log"
_NAMESPACE = "alerts"


def _dedupe_key(title: str, message: str) -> str:
    return hashlib.sha256(f"{title}|{message}".encode("utf-8")).hexdigest()[:20]


def send(title: str, message: str, *, severity: str = "info", source: str = "system") -> dict[str, Any]:
    key = _dedupe_key(title, message)
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    record = {"key": key, "title": title, "message": message, "severity": severity,
              "source": source, "created_at": stamp, "channels": []}
    if any(r["key"] == key for r in list_state(namespace=_NAMESPACE)):
        record["channels"] = ["deduplicated"]
        return {"ok": True, **record}

    with ALERT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    record["channels"].append("file")

    webhook = os.getenv("CLOUD_OS_ALERT_WEBHOOK")
    if webhook:
        try:
            resp = requests.post(webhook, json=record, timeout=15)
            record["channels"].append(f"webhook:{resp.status_code}")
        except Exception as exc:
            record["channels"].append(f"webhook_error:{type(exc).__name__}")
    save_state(key, record, namespace=_NAMESPACE)
    return {"ok": True, **record}


def alerts(limit: int = 50) -> list[dict[str, Any]]:
    rows = list_state(namespace=_NAMESPACE)
    rows.sort(key=lambda r: r["updated_at"], reverse=True)
    return [r["payload"] for r in rows[:limit]]
