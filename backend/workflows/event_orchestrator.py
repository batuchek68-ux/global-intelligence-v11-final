"""Event-driven entrypoint: publish an event and run the operating cycle.

Designed for GitHub Actions repository_dispatch and for local event replay.
Existing cron workflows remain as a compatibility fallback.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
for p in (ROOT, BACKEND):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def run(event_type: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    from backend.services.event_bus import publish
    event_type = event_type or os.getenv("CLOUD_OS_EVENT_TYPE") or "daily.tick"
    payload = payload or {}
    raw = os.getenv("CLOUD_OS_EVENT_PAYLOAD")
    if raw and not payload:
        try:
            parsed = json.loads(raw)
            payload = parsed if isinstance(parsed, dict) else {}
        except Exception:
            payload = {"raw": raw}
    event = publish(event_type, payload)

    from backend.workflows.daily_job import run_daily_cycle
    summary = run_daily_cycle()
    publish("daily_cycle.completed", {
        "event_id": event["id"],
        "project_count": summary.get("project_count"),
        "case_count": summary.get("case_count"),
    })
    return {"ok": True, "trigger": event, "summary": summary}


def main() -> None:
    result = run()
    print(f"[event_orchestrator] ok={result['ok']} trigger={result['trigger']['type']}")


if __name__ == "__main__":
    main()
