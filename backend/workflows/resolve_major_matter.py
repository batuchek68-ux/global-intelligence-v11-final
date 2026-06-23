from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.decision import resolve_major_matter
from core.storage import ensure_dirs
from comm.github_issue import build_decision_receipt, maybe_close_issue, maybe_comment_issue


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve a major matter after owner decision.")
    parser.add_argument("--project", default=os.getenv("MAJOR_MATTER_PROJECT", ""))
    parser.add_argument("--reply", default=os.getenv("OWNER_REPLY", ""))
    parser.add_argument("--source", default=os.getenv("OWNER_REPLY_SOURCE", "manual"))
    parser.add_argument("--issue-number", default=os.getenv("OWNER_REPLY_ISSUE_NUMBER", ""))
    args = parser.parse_args()

    ensure_dirs()
    if not args.project:
        raise SystemExit("--project or MAJOR_MATTER_PROJECT is required")
    if not args.reply:
        raise SystemExit("--reply or OWNER_REPLY is required")

    result = resolve_major_matter(args.project, args.reply, args.source)
    if not result["resolved"]:
        raise SystemExit(result["reason"])
    print(f"Resolved major matter: {result['project']} -> {result['decision']}")
    print(f"Decision record: {result['decision_path']}")
    print(f"Continuation: {result['continuation_path']}")
    comment_result = maybe_comment_issue(args.issue_number, build_decision_receipt(result))
    print(f"GitHub issue receipt: {comment_result}")
    close_result = maybe_close_issue(args.issue_number)
    print(f"GitHub issue close: {close_result}")


if __name__ == "__main__":
    main()
