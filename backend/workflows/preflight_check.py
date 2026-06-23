from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    ".github/workflows/international_trade_ops.yml",
    ".github/workflows/owner_decision.yml",
    ".github/workflows/watchdog.yml",
    ".github/workflows/cloud_acceptance.yml",
    ".github/workflows/codex_autonomous_repair.yml",
    "cloud.local.example.json",
    "cloud.env.example.ps1",
    "check-cloud-config.cmd",
    "check-cloud-config.ps1",
    "run-cloud-test.cmd",
    "run-cloud-test.ps1",
    "setup-cloud-test.ps1",
    "运行云端测试.cmd",
    "运行云端测试.ps1",
    "workflows/daily_job.py",
    "workflows/cloud_acceptance.py",
    "workflows/trigger_cloud_acceptance.py",
    "workflows/upload_and_trigger_cloud.py",
    "workflows/create_repo_upload_and_trigger.py",
    "workflows/cloud_connection_check.py",
    "workflows/cloud_config.py",
    "workflows/cloud_run.py",
    "workflows/cloud_test_status.py",
    "workflows/ensure_labels.py",
    "workflows/persist_state.py",
    "workflows/prepare_release.py",
    "workflows/publish_summary.py",
    "workflows/resolve_major_matter.py",
    "workflows/watchdog.py",
    "workflows/autonomous_repair.py",
    "core/business_flow.py",
    "core/operator.py",
    "core/decision.py",
    "core/executor.py",
    "core/report.py",
    "comm/github_issue.py",
    "comm/notification.py",
    "comm/wechat.py",
    "projects/templates/project_intake.md",
    "README.md",
    "docs/github-headquarters.md",
    "docs/github-deployment-runbook.md",
    "docs/cloud-run.md",
    "docs/github-token-setup.md",
]

REQUIRED_DIRS = [
    "comm/outbox",
    "memory/cases",
    "memory/decisions",
    "memory/execution_logs",
    "memory/continuations",
    "memory/operator_logs",
    "reports",
    "reports/business_flows",
    "research/briefs",
    "media/drafts",
]

REQUIRED_TEXT = {
    ".github/workflows/international_trade_ops.yml": [
        "workflow_dispatch",
        "schedule:",
        "contents: write",
        "python workflows/ensure_labels.py",
        "python workflows/daily_job.py",
        "python workflows/publish_summary.py",
        "python workflows/persist_state.py",
        "reports/",
    ],
    ".github/workflows/owner_decision.yml": [
        "issue_comment",
        "/approve",
        "/reject",
        "/revise",
        "OWNER_REPLY_ISSUE_NUMBER",
        "python workflows/resolve_major_matter.py",
        "python workflows/persist_state.py",
    ],
    ".github/workflows/watchdog.yml": [
        "0 */6 * * *",
        "contents: write",
        "python workflows/watchdog.py",
        "python workflows/persist_state.py",
        "GITHUB_STEP_SUMMARY",
    ],
    ".github/workflows/codex_autonomous_repair.yml": [
        "workflow_dispatch",
        "schedule:",
        "python workflows/autonomous_repair.py",
        "python workflows/persist_state.py",
        "reports/autonomous_repair.md",
    ],
    ".github/workflows/cloud_acceptance.yml": [
        "workflow_dispatch",
        "contents: write",
        "python workflows/preflight_check.py",
        "python -m unittest discover -s tests",
        "python workflows/daily_job.py",
        "python workflows/watchdog.py",
        "python workflows/cloud_acceptance.py",
        "python workflows/persist_state.py",
        "reports/cloud_acceptance.md",
    ],
    ".gitignore": [
        "cloud.local.json",
        "cloud.env.ps1",
    ],
    "cloud.local.example.json": [
        "repository",
        "branch",
    ],
    "cloud.env.example.ps1": [
        "GITHUB_REPOSITORY",
        "owner/repository",
    ],
    "运行云端测试.ps1": [
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "run-cloud-test.ps1",
    ],
    "run-cloud-test.ps1": [
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "Read-Host",
        "SecureString",
        "PromptToken",
        "cloud.local.json",
        "cloud_run.py",
        "cloud_test_status.py",
        "CreateRepo",
    ],
    "check-cloud-config.ps1": [
        "cloud_connection_check.py",
        "cloud_test_status.py",
    ],
    "check-cloud-config.cmd": [
        "ExecutionPolicy Bypass",
        "check-cloud-config.ps1",
    ],
    "run-cloud-test.cmd": [
        "ExecutionPolicy Bypass",
        "run-cloud-test.ps1",
    ],
    "setup-cloud-test.ps1": [
        "Read-Host",
        "SecureString",
        "SaveRepository",
        "cloud.local.json",
        "run-cloud-test.ps1",
        "cloud_test_status.py",
        "CreateRepo",
        "Upload",
    ],
    "运行云端测试.cmd": [
        "ExecutionPolicy Bypass",
        "run-cloud-test.ps1",
    ],
    "workflows/cloud_acceptance.py": [
        "GitHub Cloud Acceptance",
        "cloud AI headquarters",
        "24h autonomous executive",
        "decides only major matters",
        "reports/cloud_acceptance.md",
        "reports/cloud_acceptance.json",
    ],
    "workflows/trigger_cloud_acceptance.py": [
        "Trigger GitHub Cloud Acceptance",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "cloud_acceptance.yml",
        "/actions/workflows/",
        "reports/cloud_acceptance_remote.json",
    ],
    "workflows/upload_and_trigger_cloud.py": [
        "Upload this project to GitHub",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "confirm-upload",
        "trigger_cloud_acceptance",
        "reports/cloud_upload_and_acceptance.json",
    ],
    "workflows/create_repo_upload_and_trigger.py": [
        "Create a GitHub repo",
        "create-repo",
        "confirm-upload",
        "upload_and_trigger",
        "reports/cloud_create_upload_and_acceptance.json",
    ],
    "workflows/cloud_connection_check.py": [
        "Read-only GitHub cloud connection check",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "configured_repository",
        "cloud_connection_check.json",
        "cloud_acceptance.yml",
    ],
    "workflows/cloud_config.py": [
        "cloud.local.json",
        "cloud.local.example.json",
        "configured_repository",
        "configured_branch",
    ],
    "workflows/cloud_run.py": [
        "Run the complete GitHub cloud test path",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
        "cloud_run.json",
        "create_upload_and_trigger",
        "trigger_cloud_acceptance",
    ],
    "workflows/cloud_test_status.py": [
        "Cloud Test Status",
        "cloud_test_status.json",
        "cloud_test_status.md",
        "completion_evidence_required",
        "run-cloud-test.cmd",
    ],
    "workflows/resolve_major_matter.py": [
        "maybe_close_issue",
        "GitHub issue close",
    ],
    "workflows/autonomous_repair.py": [
        "Codex / AI Autonomous Repair Report",
        "workflows/preflight_check.py",
        "python",
        "reports/autonomous_repair.md",
    ],
    "core/business_flow.py": [
        "WeChat",
        "QQ Meeting",
        "Douyin",
        "Video Channel",
        "TikTok",
        "YouTube",
    ],
    "comm/notification.py": [
        "WECHAT_WEBHOOK_URL",
        "FEISHU_WEBHOOK_URL",
        "SMTP_HOST",
        "ALERT_EMAIL_TO",
    ],
    "README.md": [
        "GitHub = 你的云端 AI 总部",
        "Codex = 24h 自主执行官",
        "你 = 只在“重大事项”出现时做决定",
        "workflows/ensure_labels.py",
        "python workflows\\prepare_release.py",
        "reports/headquarters_status.md",
        "reports/owner_inbox.md",
        "memory/execution_logs",
        "docs/github-deployment-runbook.md",
        "GitHub Cloud Acceptance",
    ],
    "docs/github-deployment-runbook.md": [
        "GitHub 上线运行手册",
        "International Trade AI Ops",
        "Owner Decision Handler",
        "24h Codex Watchdog",
        "GitHub Cloud Acceptance",
        "reports/headquarters_status.md",
        "reports/owner_inbox.md",
        "reports/cloud_acceptance.md",
        "memory/execution_logs",
        "trigger_cloud_acceptance.py",
        "upload_and_trigger_cloud.py",
        "create_repo_upload_and_trigger.py",
        "cloud_connection_check.py",
    ],
    "docs/cloud-run.md": [
        "One Command Cloud Test",
        ".\\run-cloud-test.cmd -Upload",
        "setup-cloud-test.ps1",
        "SaveRepository",
        "reports/cloud_run.json",
        "GitHub Cloud Acceptance",
    ],
    "docs/github-token-setup.md": [
        "GitHub Token Setup",
        "GITHUB_TOKEN or GH_TOKEN",
        "GITHUB_REPOSITORY",
        "cloud.env.example.ps1",
        "cloud.env.ps1",
        "Contents: Read and write",
        "Actions: Read and write",
        "workflow",
        "run-cloud-test.cmd -CreateRepo",
        "SaveRepository",
    ],
}


def check() -> dict:
    results = []
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        results.append({"check": f"file:{relative}", "ok": path.is_file()})

    for relative in REQUIRED_DIRS:
        path = ROOT / relative
        results.append({"check": f"dir:{relative}", "ok": path.is_dir()})

    for relative, needles in REQUIRED_TEXT.items():
        path = ROOT / relative
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        for needle in needles:
            results.append({"check": f"text:{relative}:{needle}", "ok": needle in text})

    ok = all(item["ok"] for item in results)
    return {"ok": ok, "results": results}


def main() -> None:
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        failed = [item["check"] for item in result["results"] if not item["ok"]]
        print("Preflight failed:", ", ".join(failed), file=sys.stderr)
        raise SystemExit(1)
    print("Preflight passed: GitHub headquarters is ready to run.")


if __name__ == "__main__":
    main()
