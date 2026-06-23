from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_RELATIVE = "cloud.local.json"
CONFIG_EXAMPLE_RELATIVE = "cloud.local.example.json"
CONFIG_PATH = ROOT / CONFIG_RELATIVE
GIT_CONFIG_PATH = ROOT / ".git" / "config"


def valid_repository_name(repository: str | None) -> bool:
    if not repository or repository.count("/") != 1:
        return False
    owner, name = repository.split("/", 1)
    if owner != owner.strip() or name != name.strip():
        return False
    if not owner or not name:
        return False
    if owner.lower() in {"owner", "yourname", "username"} or name.lower() in {"repository", "repo"}:
        return False
    pattern = r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}[A-Za-z0-9])?$"
    repo_pattern = r"^[A-Za-z0-9._-]+$"
    return bool(re.match(pattern, owner) and re.match(repo_pattern, name))


def repository_format_hint() -> str:
    return "Repository must be a real GitHub owner/repository, for example octocat/international-trade-ai."


def load_cloud_config(path: Path = CONFIG_PATH) -> dict:
    report_path = CONFIG_RELATIVE if path == CONFIG_PATH else str(path)
    if not path.exists():
        return {"exists": False, "path": report_path}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"exists": True, "path": report_path, "error": str(exc)}
    return {
        "exists": True,
        "path": report_path,
        "repository": data.get("repository"),
        "branch": data.get("branch", "main"),
    }


def repository_from_remote_url(remote_url: str | None) -> str | None:
    if not remote_url:
        return None
    value = remote_url.strip()
    patterns = [
        r"^https://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?$",
        r"^git@github\.com:([^/\s]+)/([^/\s]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?$",
    ]
    for pattern in patterns:
        match = re.match(pattern, value)
        if match:
            repository = f"{match.group(1)}/{match.group(2)}"
            return repository if valid_repository_name(repository) else None
    return None


def repository_from_git_config(path: Path = GIT_CONFIG_PATH) -> str | None:
    if not path.exists():
        return None
    in_origin = False
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if line.startswith("["):
            in_origin = line == '[remote "origin"]'
            continue
        if in_origin and line.startswith("url"):
            _, _, remote_url = line.partition("=")
            return repository_from_remote_url(remote_url)
    return None


def configured_repository(default: str | None = None) -> str | None:
    return default or load_cloud_config().get("repository") or repository_from_git_config()


def configured_branch(default: str | None = None) -> str:
    return default or load_cloud_config().get("branch") or "main"


def token_from_gh_cli() -> str | None:
    if not shutil.which("gh"):
        return None
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    token = result.stdout.strip()
    if result.returncode == 0 and token:
        return token
    return None


def configured_token(default: str | None = None) -> str | None:
    token, _ = configured_token_info(default)
    return token


def token_source(default: str | None = None) -> str:
    _, source = configured_token_info(default)
    return source


def configured_token_info(default: str | None = None) -> tuple[str | None, str]:
    if default:
        return default, "environment"
    gh_token = token_from_gh_cli()
    if gh_token:
        return gh_token, "gh-cli"
    return None, "missing"
