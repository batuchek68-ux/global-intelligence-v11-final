from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "headquarters_status.md"
OWNER_INBOX = ROOT / "reports" / "owner_inbox.md"


def publish_summary() -> dict:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return {"published": False, "reason": "GITHUB_STEP_SUMMARY not configured"}
    if not REPORT.exists():
        return {"published": False, "reason": "headquarters report not found"}

    with open(summary_path, "a", encoding="utf-8") as handle:
        if OWNER_INBOX.exists():
            handle.write(OWNER_INBOX.read_text(encoding="utf-8"))
            handle.write("\n\n---\n\n")
        handle.write(REPORT.read_text(encoding="utf-8"))
        handle.write("\n")
    return {"published": True, "summary_path": summary_path}


def main() -> None:
    print(publish_summary())


if __name__ == "__main__":
    main()
