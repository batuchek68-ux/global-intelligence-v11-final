from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAST_RUN = ROOT / "memory" / "last_run.json"
OWNER_INBOX = ROOT / "reports" / "owner_inbox.md"
WATCHDOG_REPORT = ROOT / "reports" / "watchdog_status.md"


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_watchdog_status(max_age_hours: int = 26) -> dict:
    if not LAST_RUN.exists():
        return {
            "ok": False,
            "reason": "memory/last_run.json not found",
            "waiting_for_owner": None,
            "age_hours": None,
        }

    summary = json.loads(LAST_RUN.read_text(encoding="utf-8"))
    created_at = parse_time(summary.get("created_at", ""))
    now = datetime.now(timezone.utc)
    age_hours = None
    fresh = False
    if created_at:
        age_hours = round((now - created_at).total_seconds() / 3600, 2)
        fresh = age_hours <= max_age_hours

    waiting_for_owner = 0
    for case in summary.get("cases", []):
        if case.get("classification", {}).get("is_major_matter") and not case.get("owner_decision"):
            waiting_for_owner += 1

    return {
        "ok": fresh and waiting_for_owner == 0,
        "reason": "healthy" if fresh and waiting_for_owner == 0 else "attention required",
        "created_at": summary.get("created_at"),
        "age_hours": age_hours,
        "max_age_hours": max_age_hours,
        "waiting_for_owner": waiting_for_owner,
        "project_count": summary.get("project_count", 0),
        "major_matter_count": summary.get("major_matter_count", 0),
        "resolved_major_matter_count": summary.get("resolved_major_matter_count", 0),
    }


def render_watchdog_report(status: dict) -> str:
    owner_inbox_hint = "reports/owner_inbox.md"
    return "\n".join(
        [
            "# 24h Codex Watchdog",
            "",
            f"- Status: {'OK' if status.get('ok') else 'ATTENTION'}",
            f"- Reason: {status.get('reason')}",
            f"- Last run: {status.get('created_at')}",
            f"- Last run age hours: {status.get('age_hours')}",
            f"- Max allowed age hours: {status.get('max_age_hours')}",
            f"- Waiting for owner: {status.get('waiting_for_owner')}",
            f"- Projects: {status.get('project_count')}",
            f"- Major matters: {status.get('major_matter_count')}",
            f"- Resolved major matters: {status.get('resolved_major_matter_count')}",
            "",
            f"Owner inbox: `{owner_inbox_hint}`",
            "",
        ]
    )


def run_watchdog() -> dict:
    status = build_watchdog_status()
    WATCHDOG_REPORT.parent.mkdir(parents=True, exist_ok=True)
    WATCHDOG_REPORT.write_text(render_watchdog_report(status), encoding="utf-8")
    return status


def main() -> None:
    status = run_watchdog()
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
