"""In-process event bus with a durable event log.

Publishers write events to the transactional state store; subscribers registered
in this process receive them immediately. This is the first step away from
independent cron scripts toward event-driven orchestration.
"""
from __future__ import annotations

import json
import os
import secrets
import time
import threading
from typing import Any, Callable

from backend.services.state_repository import list_state, save_state

_LOCK = threading.RLock()
_SUBSCRIBERS: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
_NAMESPACE = "events"


def reset_subscribers() -> None:
    with _LOCK:
        _SUBSCRIBERS.clear()


def subscribe(event_type: str, handler: Callable[[dict[str, Any]], None]) -> None:
    with _LOCK:
        _SUBSCRIBERS.setdefault(event_type, []).append(handler)


def _maybe_alert(event_type: str, payload: dict[str, Any]) -> None:
    configured = {
        t.strip() for t in os.getenv("CLOUD_OS_ALERT_EVENTS", "risk.detected").split(",") if t.strip()
    }
    if event_type not in configured:
        return
    try:
        from backend.services.alert_service import send
        send(f"Event: {event_type}", json.dumps(payload, ensure_ascii=False)[:600],
             severity="warning", source="event_bus")
    except Exception:
        pass


def publish(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    event = {
        "id": secrets.token_hex(12),
        "type": event_type,
        "ts": int(time.time()),
        "payload": payload,
        "status": "published",
    }
    save_state(f"{event_type}::{event['id']}", event, namespace=_NAMESPACE)
    _maybe_alert(event_type, payload or {})
    with _LOCK:
        handlers = list(_SUBSCRIBERS.get(event_type, []))
    for handler in handlers:
        try:
            handler(event)
        except Exception:
            pass
    return event


def list_events(event_type: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    rows = list_state(namespace=_NAMESPACE)
    if event_type:
        rows = [r for r in rows if r["key"].startswith(f"{event_type}::")]
    rows.sort(key=lambda r: r["updated_at"], reverse=True)
    return [r["payload"] for r in rows[:limit]]


def health() -> dict[str, Any]:
    with _LOCK:
        types = {k for k, v in _SUBSCRIBERS.items() if v}
    return {"ok": True, "subscribed_types": sorted(types), "events": len(list_events(limit=1))}
