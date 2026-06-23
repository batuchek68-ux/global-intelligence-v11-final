from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflows.cloud_connection_check import build_connection_check
from workflows.cloud_config import configured_branch, configured_repository, configured_token_info, repository_format_hint, valid_repository_name
from workflows.create_repo_upload_and_trigger import create_upload_and_trigger
from workflows.trigger_cloud_acceptance import trigger_cloud_acceptance
from workflows.upload_and_trigger_cloud import upload_and_trigger

REPORT_RELATIVE = "reports/cloud_run.json"
REPORT = ROOT / REPORT_RELATIVE


def missing_configuration(repository: str | None, token: str | None, token_source_name: str = "unknown") -> dict:
    missing = []
    if not token:
        missing.append("GITHUB_TOKEN or GH_TOKEN")
    if not repository:
        missing.append("GITHUB_REPOSITORY or --repository owner/name")
    return {
        "ok": False,
        "stage": "configuration",
        "reason": "Set " + ", and ".join(missing) + ".",
        "missing": missing,
        "next_command": ".\\run-cloud-test.cmd -Upload",
        "interactive_command": "powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\setup-cloud-test.ps1",
        "manual_environment": [
            '$env:GITHUB_TOKEN = "your GitHub token"',
            '$env:GITHUB_REPOSITORY = "owner/repository"',
            ".\\run-cloud-test.cmd -Upload",
        ],
        "python_command": "python workflows\\cloud_run.py --upload --confirm-upload",
        "token_source": token_source_name,
    }


def build_cloud_run(
    repository: str | None,
    token: str | None,
    branch: str = "main",
    create_repo: bool = False,
    private: bool = True,
    confirm_upload: bool = False,
    upload: bool = False,
    trigger: bool = True,
    token_source_name: str = "unknown",
) -> dict:
    if not token or not repository:
        return missing_configuration(repository, token, token_source_name=token_source_name)
    if not valid_repository_name(repository):
        return {"ok": False, "stage": "configuration", "reason": repository_format_hint()}

    result: dict = {
        "ok": False,
        "stage": "started",
        "repository": repository,
        "branch": branch,
        "token_source": token_source_name,
        "plan": {
            "connection_check": True,
            "create_repo": create_repo,
            "upload": upload or create_repo,
            "trigger": trigger,
        },
    }

    connection = build_connection_check(repository, token, token_source_name=token_source_name)
    result["connection"] = connection
    if not connection.get("ok") and connection.get("stage") == "token":
        result["ok"] = False
        result["stage"] = "authentication_failed"
        result["reason"] = (
            "GitHub returned 401 Bad credentials. The token is invalid, expired, revoked, "
            "or lacks access. Run with -PromptToken and paste a newly generated token."
        )
        return result

    if connection.get("ok") and trigger and not upload and not create_repo:
        acceptance = trigger_cloud_acceptance(repository=repository, token=token, ref=branch)
        result["acceptance"] = acceptance
        result["ok"] = bool(acceptance.get("ok"))
        result["stage"] = "accepted" if result["ok"] else "acceptance_failed"
        return result

    if connection.get("ok") and not trigger and not upload and not create_repo:
        result["ok"] = True
        result["stage"] = "ready"
        return result

    if create_repo:
        create_upload = create_upload_and_trigger(
            repository=repository,
            token=token,
            branch=branch,
            create_repo=True,
            private=private,
            confirm_upload=confirm_upload,
            trigger=trigger,
        )
        result["create_upload_and_acceptance"] = create_upload
        result["ok"] = bool(create_upload.get("ok"))
        result["stage"] = "accepted" if result["ok"] else "create_upload_or_acceptance_failed"
        return result

    if upload:
        upload_result = upload_and_trigger(
            repository=repository,
            token=token,
            branch=branch,
            confirm_upload=confirm_upload,
            trigger=trigger,
        )
        result["upload_and_acceptance"] = upload_result
        result["ok"] = bool(upload_result.get("ok"))
        result["stage"] = "accepted" if result["ok"] else "upload_or_acceptance_failed"
        return result

    result["stage"] = connection.get("stage", "connection_failed")
    result["reason"] = (
        "Cloud connection is not ready. Use --upload --confirm-upload for an existing repo, "
        "or --create-repo --confirm-upload when the repo does not exist."
    )
    return result


def write_report(result: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def nested_get(data: dict, *keys: str) -> object | None:
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def render_summary(result: dict) -> str:
    acceptance = result.get("acceptance")
    if not isinstance(acceptance, dict):
        acceptance = nested_get(result, "upload_and_acceptance", "acceptance")
    if not isinstance(acceptance, dict):
        acceptance = nested_get(result, "create_upload_and_acceptance", "upload_and_acceptance", "acceptance")
    if not isinstance(acceptance, dict):
        acceptance = {}

    upload = result.get("upload_and_acceptance")
    if not isinstance(upload, dict):
        upload = nested_get(result, "create_upload_and_acceptance", "upload_and_acceptance")
    upload_stats = upload.get("upload") if isinstance(upload, dict) else {}
    if not isinstance(upload_stats, dict):
        upload_stats = {}

    lines = [
        "Cloud test summary",
        f"- ok: {bool(result.get('ok'))}",
        f"- stage: {result.get('stage')}",
        f"- repository: {result.get('repository', '')}",
        f"- branch: {result.get('branch', '')}",
        f"- report: {REPORT_RELATIVE}",
    ]
    if upload_stats:
        lines.extend(
            [
                f"- files: {upload_stats.get('uploaded', 0)}/{upload_stats.get('file_count', 0)} uploaded",
                f"- written: {upload_stats.get('written', 0)}",
                f"- skipped: {upload_stats.get('skipped', 0)}",
                f"- attempted: {upload_stats.get('attempted', upload_stats.get('file_count', 0))}",
                f"- failed uploads: {len(upload_stats.get('failed') or [])}",
            ]
        )
    if acceptance:
        lines.extend(
            [
                f"- conclusion: {acceptance.get('conclusion')}",
                f"- run_url: {acceptance.get('run_url')}",
            ]
        )
        jobs = acceptance.get("jobs")
        failed_steps = jobs.get("failed_steps") if isinstance(jobs, dict) else []
        if failed_steps:
            lines.append("- failed steps:")
            for step in failed_steps:
                lines.append(f"  - {step.get('job')} / {step.get('step')}")
    if not result.get("ok"):
        reason = result.get("reason")
        if not reason and isinstance(upload_stats, dict):
            reason = upload_stats.get("reason")
        if reason:
            lines.append(f"- reason: {reason}")
        lines.append("- next: check reports/cloud_run.json for full details")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the complete GitHub cloud test path.")
    parser.add_argument("--repository", default=configured_repository(os.getenv("GITHUB_REPOSITORY")), help="GitHub repository as owner/name.")
    parser.add_argument("--branch", default=configured_branch(os.getenv("GITHUB_REF_NAME")))
    parser.add_argument("--create-repo", action="store_true", help="Create the GitHub repo when it is missing.")
    parser.add_argument("--public", action="store_true", help="Create a public repo instead of a private one.")
    parser.add_argument("--upload", action="store_true", help="Upload the current project before triggering acceptance.")
    parser.add_argument("--confirm-upload", action="store_true", help="Confirm uploading local files to GitHub.")
    parser.add_argument("--no-trigger", action="store_true", help="Check or upload only; do not run cloud acceptance.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token, source = configured_token_info(os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"))
    result = build_cloud_run(
        repository=args.repository,
        token=token,
        branch=args.branch,
        create_repo=args.create_repo,
        private=not args.public,
        confirm_upload=args.confirm_upload,
        upload=args.upload,
        trigger=not args.no_trigger,
        token_source_name=source,
    )
    write_report(result)
    print(render_summary(result))
    if not result.get("ok"):
        raise SystemExit(1 if result.get("stage") != "configuration" else 2)


if __name__ == "__main__":
    main()
