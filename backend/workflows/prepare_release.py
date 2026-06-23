from __future__ import annotations

import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PACKAGE = DIST / "global-intelligence-v11.zip"
MANIFEST = DIST / "release_manifest.json"

EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".venv", "dist"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def collect_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*") if should_include(path))


def build_release() -> dict:
    DIST.mkdir(parents=True, exist_ok=True)
    files = collect_files()
    with zipfile.ZipFile(PACKAGE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())

    manifest = {
        "package": str(PACKAGE),
        "file_count": len(files),
        "files": [path.relative_to(ROOT).as_posix() for path in files],
        "upload_steps": [
            "Create a new GitHub repository.",
            "Upload or unzip global-intelligence-v11.zip into the repository root.",
            "Enable GitHub Actions.",
            "Run International Trade AI Ops from Actions.",
            "Run GitHub Cloud Acceptance from Actions to verify the cloud headquarters.",
            "Optionally run .\\check-cloud-config.cmd or python workflows/cloud_connection_check.py first to verify token, repository, and workflow visibility.",
            "For one-command cloud testing with an existing repository, set GITHUB_TOKEN and GITHUB_REPOSITORY, then run python workflows/cloud_run.py --upload --confirm-upload.",
            "For an interactive setup, run .\\setup-cloud-test.ps1 and enter the repository plus token when prompted.",
            "For a stable Windows launcher with an existing repository, run .\\run-cloud-test.cmd -Upload after setting GITHUB_TOKEN and GITHUB_REPOSITORY.",
            "On Windows, run .\\运行云端测试.ps1 -Upload after setting GITHUB_TOKEN and GITHUB_REPOSITORY.",
            "Or set GITHUB_TOKEN and GITHUB_REPOSITORY, then run python workflows/trigger_cloud_acceptance.py.",
            "To upload without git/gh, run python workflows/upload_and_trigger_cloud.py --confirm-upload.",
            "To create a missing repo too, run python workflows/create_repo_upload_and_trigger.py --create-repo --confirm-upload.",
            "Reply to major-matter Issues with /approve, /reject, or /revise.",
        ],
        "verification_steps": [
            "Run the GitHub Cloud Acceptance workflow and confirm reports/cloud_acceptance.md says PASS.",
            "Open the Actions run summary and confirm reports/owner_inbox.md appears first.",
            "Confirm reports/headquarters_status.md lists scanned projects and execution status.",
            "Confirm memory/execution_logs contains one JSON record for each processed project.",
            "Run 24h Codex Watchdog manually once and confirm reports/watchdog_status.md is committed back.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    manifest = build_release()
    print(f"Release package: {manifest['package']}")
    print(f"Files packaged: {manifest['file_count']}")
    print(f"Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
