from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflows.cloud_config import configured_repository, configured_token
from workflows.upload_and_trigger_cloud import upload_and_trigger

REPORT_RELATIVE = "reports/cloud_create_upload_and_acceptance.json"
REPORT = ROOT / REPORT_RELATIVE


def github_api_request(method: str, path: str, token: str, payload: dict | None = None) -> tuple[int, dict | str | None]:
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            if not body:
                return response.status, None
            return response.status, json.loads(body)
    except Exception as exc:
        if hasattr(exc, "read"):
            body = exc.read().decode("utf-8")
            try:
                return getattr(exc, "code", 0), json.loads(body) if body else {}
            except json.JSONDecodeError:
                return getattr(exc, "code", 0), body
        return 0, str(exc)


def repository_exists(repository: str, token: str) -> dict:
    status, data = github_api_request("GET", f"/repos/{repository}", token)
    return {"exists": status == 200, "status": status, "data": data}


def create_repository(owner: str, name: str, token: str, private: bool = True) -> dict:
    status, data = github_api_request(
        "POST",
        "/user/repos",
        token,
        {
            "name": name,
            "private": private,
            "auto_init": False,
            "description": "International Trade AI cloud headquarters.",
        },
    )
    return {"created": status == 201, "status": status, "data": data, "repository": f"{owner}/{name}"}


def ensure_repository(repository: str, token: str, private: bool = True, create_if_missing: bool = False) -> dict:
    exists = repository_exists(repository, token)
    if exists["exists"]:
        return {"ok": True, "stage": "exists", "repository": repository, "details": exists}

    if not create_if_missing:
        return {
            "ok": False,
            "stage": "missing",
            "repository": repository,
            "reason": "Repository does not exist or token cannot access it. Pass --create-repo to create it.",
            "details": exists,
        }

    owner, name = repository.split("/", 1)
    created = create_repository(owner, name, token, private=private)
    return {
        "ok": created["created"],
        "stage": "created" if created["created"] else "create_failed",
        "repository": repository,
        "details": created,
    }


def create_upload_and_trigger(
    repository: str,
    token: str,
    branch: str = "main",
    create_repo: bool = False,
    private: bool = True,
    confirm_upload: bool = False,
    trigger: bool = True,
) -> dict:
    if "/" not in repository:
        return {"ok": False, "stage": "configuration", "reason": "Repository must be owner/name."}

    ensure = ensure_repository(repository, token, private=private, create_if_missing=create_repo)
    if not ensure["ok"]:
        return {"ok": False, "stage": "repository", "repository": repository, "ensure": ensure}

    upload = upload_and_trigger(
        repository=repository,
        token=token,
        branch=branch,
        confirm_upload=confirm_upload,
        trigger=trigger,
    )
    return {
        "ok": upload.get("ok", False),
        "stage": "accepted" if upload.get("ok") else "upload_or_acceptance_failed",
        "repository": repository,
        "branch": branch,
        "ensure": ensure,
        "upload_and_acceptance": upload,
    }


def write_report(result: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a GitHub repo if needed, upload this project, and run cloud acceptance.")
    parser.add_argument("--repository", default=configured_repository(os.getenv("GITHUB_REPOSITORY")), help="GitHub repository as owner/name.")
    parser.add_argument("--branch", default=os.getenv("GITHUB_REF_NAME", "main"))
    parser.add_argument("--create-repo", action="store_true")
    parser.add_argument("--public", action="store_true", help="Create public repo instead of private when --create-repo is used.")
    parser.add_argument("--confirm-upload", action="store_true")
    parser.add_argument("--no-trigger", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = configured_token(os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN"))
    if not token or not args.repository:
        result = {
            "ok": False,
            "stage": "configuration",
            "reason": "Set GITHUB_TOKEN or GH_TOKEN, and GITHUB_REPOSITORY or --repository owner/name.",
        }
        write_report(result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(2)

    result = create_upload_and_trigger(
        repository=args.repository,
        token=token,
        branch=args.branch,
        create_repo=args.create_repo,
        private=not args.public,
        confirm_upload=args.confirm_upload,
        trigger=not args.no_trigger,
    )
    write_report(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
