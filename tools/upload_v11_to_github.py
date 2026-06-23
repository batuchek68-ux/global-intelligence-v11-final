from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = os.getenv("GITHUB_REPOSITORY", "batuchek68-ux/global-intelligence-v11")
BRANCH = os.getenv("GITHUB_BRANCH", "main")

EXCLUDED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    "work",
    ".codex",
    ".agents",
}
EXCLUDED_SUFFIXES = {".pyc", ".log", ".zip", ".exe", ".msi"}
EXCLUDED_FILES = {"cloud.local.json", "cloud.env.ps1", ".env"}


def github_request(method: str, path: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    url = f"https://api.github.com/repos/{REPOSITORY}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=40) as response:
            body = response.read().decode("utf-8") or "{}"
            return response.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") or "{}"
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"message": body}
        return exc.code, parsed


def should_upload(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    parts = set(relative.parts)
    if parts & EXCLUDED_DIRS:
        return False
    if path.name in EXCLUDED_FILES or path.name.startswith(".env."):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return path.is_file()


def iter_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*") if should_upload(path))


def remote_sha(relative: str, token: str) -> str | None:
    encoded = urllib.parse.quote(relative)
    status, data = github_request("GET", f"/contents/{encoded}?ref={urllib.parse.quote(BRANCH)}", token)
    if status == 200:
        return data.get("sha")
    if status == 404:
        return None
    raise RuntimeError(f"GitHub returned {status} for {relative}: {data}")


def upload_file(path: Path, token: str) -> dict:
    relative = path.relative_to(ROOT).as_posix()
    sha = remote_sha(relative, token)
    payload = {
        "message": f"v11 architecture sync: {relative}",
        "content": base64.b64encode(path.read_bytes()).decode("ascii"),
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha
    status, data = github_request("PUT", f"/contents/{urllib.parse.quote(relative)}", token, payload)
    return {"path": relative, "ok": status in (200, 201), "status": status, "message": data.get("message")}


def main() -> int:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        print("Set GITHUB_TOKEN or GH_TOKEN in PowerShell before uploading.", file=sys.stderr)
        return 2

    results = [upload_file(path, token) for path in iter_files()]
    failed = [item for item in results if not item["ok"]]
    print(json.dumps({"repository": REPOSITORY, "branch": BRANCH, "files": len(results), "failed": failed}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
