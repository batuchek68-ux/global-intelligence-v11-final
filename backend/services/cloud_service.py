from __future__ import annotations

from typing import Any

from backend.services.report_service import read_json_report, read_text_report


def cloud_status() -> dict[str, Any]:
    status = read_json_report("reports/cloud_test_status.json")
    return {
        "ok": bool(status.get("data", {}).get("ok")) if isinstance(status.get("data"), dict) else False,
        "status_report": read_text_report("reports/cloud_test_status.md"),
        "raw": status,
    }


def cloud_check() -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "local_status_read",
        "status": cloud_status(),
        "note": "Remote GitHub execution requires GITHUB_TOKEN/GH_TOKEN and GITHUB_REPOSITORY in the runtime environment.",
    }


def cloud_run_requested() -> dict[str, Any]:
    return {
        "ok": False,
        "stage": "approval_required",
        "reason": "Cloud mutation is not triggered from the API in this local architecture pass.",
        "next": "Run the GitHub Actions workflow or backend/workflows/cloud_run.py with runtime secrets in PowerShell.",
    }
