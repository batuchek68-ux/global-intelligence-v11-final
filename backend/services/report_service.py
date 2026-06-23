from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_text_report(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    if not path.exists():
        return {"exists": False, "path": relative_path, "content": ""}
    return {"exists": True, "path": relative_path, "content": path.read_text(encoding="utf-8", errors="replace")}


def read_json_report(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    if not path.exists():
        return {"exists": False, "path": relative_path, "data": None}
    try:
        return {"exists": True, "path": relative_path, "data": json.loads(path.read_text(encoding="utf-8"))}
    except json.JSONDecodeError as exc:
        return {"exists": True, "path": relative_path, "error": str(exc), "data": None}


def dashboard_summary() -> dict[str, Any]:
    return {
        "headquarters": read_text_report("reports/headquarters_status.md"),
        "owner_inbox": read_text_report("reports/owner_inbox.md"),
        "cloud_status": read_json_report("reports/cloud_test_status.json"),
        "cloud_run": read_json_report("reports/cloud_run.json"),
    }
