from __future__ import annotations

import json
import os
import urllib.request


def build_issue_payload(ticket: dict) -> dict:
    title = f"[Major Matter] {ticket['project']} requires owner decision"
    body = f"""## Decision Needed

{ticket['question']}

## Context

- Country: {ticket['country']}
- Counterparty: {ticket['counterparty']}
- Risk level: {ticket['risk_level']}
- Risk score: {ticket['risk_score']}/100
- Triggers: {", ".join(ticket.get("triggers", [])) or "none"}

## Owner Reply Format

Reply with one of:

- /approve optional notes
- /reject optional notes
- /revise conditions

Codex will continue only after the major matter is decided.
"""
    return {"title": title, "body": body, "labels": ["major-matter", "owner-decision"]}


def maybe_create_issue(ticket: dict) -> dict:
    token = os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")
    if not token or not repository:
        return {"created": False, "reason": "GITHUB_TOKEN or GITHUB_REPOSITORY not configured"}

    payload = build_issue_payload(ticket)
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/issues",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {"created": True, "number": data.get("number"), "url": data.get("html_url")}
    except Exception as exc:  # pragma: no cover - network depends on GitHub runtime.
        return {"created": False, "reason": str(exc)}


def build_decision_receipt(result: dict) -> str:
    return f"""## Codex Decision Receipt

Owner decision recorded: `{result.get('decision')}`

Codex next step has been written to:

```text
{result.get('continuation_path')}
```

Decision memory:

```text
{result.get('decision_path')}
```

Codex will continue according to the owner decision in the next operating cycle.
"""


def maybe_comment_issue(issue_number: str | int | None, body: str) -> dict:
    token = os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")
    if not token or not repository or not issue_number:
        return {"commented": False, "reason": "GITHUB_TOKEN, GITHUB_REPOSITORY, or issue number not configured"}

    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/issues/{issue_number}/comments",
        data=json.dumps({"body": body}, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {"commented": True, "url": data.get("html_url")}
    except Exception as exc:  # pragma: no cover - network depends on GitHub runtime.
        return {"commented": False, "reason": str(exc)}


def maybe_close_issue(issue_number: str | int | None) -> dict:
    token = os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")
    if not token or not repository or not issue_number:
        return {"closed": False, "reason": "GITHUB_TOKEN, GITHUB_REPOSITORY, or issue number not configured"}

    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}/issues/{issue_number}",
        data=json.dumps({"state": "closed", "state_reason": "completed"}, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {"closed": True, "state": data.get("state"), "url": data.get("html_url")}
    except Exception as exc:  # pragma: no cover - network depends on GitHub runtime.
        return {"closed": False, "reason": str(exc)}
