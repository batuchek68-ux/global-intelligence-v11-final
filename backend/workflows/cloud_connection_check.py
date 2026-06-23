from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflows.create_repo_upload_and_trigger import github_api_request
from workflows.cloud_config import configured_repository, configured_token_info, repository_format_hint, valid_repository_name
from workflows.trigger_cloud_acceptance import WORKFLOW_FILE, github_request

REPORT_RELATIVE = "reports/cloud_connection_check.json"
REPORT = ROOT / REPORT_RELATIVE
WORKFLOW_FILE_NAME = "cloud_acceptance.yml"


def redact_login(data: dict | str | None) -> dict:
    if not isinstance(data, dict):
        return {}
    return {
        "login": data.get("login"),
        "id": data.get("id"),
        "type": data.get("type"),
    }


def check_token(token: str) -> dict:
    status, data = github_api_request("GET", "/user", token)
    scopes = []
    if isinstance(data, dict):
        scopes = data.get("scopes", [])
    return {
        "ok": status == 200,
        "status": status,
        "user": redact_login(data),
        "details": data if status != 200 else None,
        "scopes": scopes,
    }


def check_repository(repository: str, token: str) -> dict:
    status, data = github_api_request("GET", f"/repos/{repository}", token)
    return {
        "ok": status == 200,
        "status": status,
        "private": data.get("private") if isinstance(data, dict) else None,
        "default_branch": data.get("default_branch") if isinstance(data, dict) else None,
        "permissions": data.get("permissions") if isinstance(data, dict) else None,
        "details": data if status != 200 else None,
    }


def check_workflow(repository: str, token: str) -> dict:
    status, data = github_request("GET", repository, f"/actions/workflows/{WORKFLOW_FILE}", token)
    return {
        "ok": status == 200,
        "status": status,
        "workflow": WORKFLOW_FILE,
        "state": data.get("state") if isinstance(data, dict) else None,
        "html_url": data.get("html_url") if isinstance(data, dict) else None,
        "details": data if status != 200 else None,
    }


def check_runs(repository: str, token: str) -> dict:
    status, data = github_request("GET", repository, "/actions/runs?per_page=1", token)
    return {
        "ok": status == 200,
        "status": status,
        "latest_run": data.get("workflow_runs", [{}])[0] if isinstance(data, dict) and data.get("workflow_runs") else None,
        "details": data if status != 200 else None,
    }


def build_connection_check(repository: str | None, token: str | None, token_source_name: str = "unknown") -> dict:
    if not token or not repository:
        missing = []
        if not token:
            missing.append("GITHUB_TOKEN or GH_TOKEN")
        if not repository:
            missing.append("GITHUB_REPOSITORY or cloud.local.json repository")
        return {
            "ok": False,
            "stage": "configuration",
            "reason": "Set GITHUB_TOKEN or GH_TOKEN, and GITHUB_REPOSITORY or --repository owner/name.",
            "missing": missing,
            "root_commands": [
                ".\\check-cloud-config-from-root.cmd",
                ".\\setup-cloud-test-from-root.cmd",
                ".\\run-cloud-test-from-root.cmd -Upload",
            ],
            "source_commands": [
                ".\\check-cloud-config.cmd",
                ".\\setup-cloud-test.ps1",
                ".\\run-cloud-test.cmd -Upload",
            ],
            "token_storage": "Token is read from environment or prompt only; do not save it to files.",
            "token_source": token_source_name,
            "checks": [],
        }
    if not valid_repository_name(repository):
        return {
            "ok": False,
            "stage": "configuration",
            "reason": repository_format_hint(),
            "checks": [],
        }

    checks = [
        {"name": "token", **check_token(token)},
        {"name": "repository", **check_repository(repository, token)},
        {"name": "workflow", **check_workflow(repository, token)},
        {"name": "actions_runs", **check_runs(repository, token)},
    ]
    ok = checks[0]["ok"] and checks[1]["ok"] and checks[2]["ok"]
    stage = "ready" if ok else next((check["name"] for check in checks if not check["ok"]), "unknown")
    return {
        "ok": ok,
        "stage": stage,
        "repository": repository,
        "workflow": WORKFLOW_FILE,
        "token_source": token_source_name,
        "checks": checks,
    }


def write_report(result: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only GitHub cloud connection check.")
    parser.add_argument("--repository", default=configured_repository(os.getenv("GITHUB_REPOSITORY")), help="GitHub repository as owner/name.")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    token, source = configured_token_info(os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"))
    result = build_connection_check(args.repository, token, token_source_name=source)
    write_report(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise SystemExit(1 if result.get("stage") != "configuration" else 2)


if __name__ == "__main__":
    main()
