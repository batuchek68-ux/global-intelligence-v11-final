from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


LABELS = {
    "major-matter": {
        "color": "b60205",
        "description": "Requires owner decision before Codex continues.",
    },
    "owner-decision": {
        "color": "d93f0b",
        "description": "Decision queue for the human owner.",
    },
    "autonomous": {
        "color": "0e8a16",
        "description": "Codex can continue without owner decision.",
    },
}


def github_request(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    token = os.getenv("GITHUB_TOKEN")
    repository = os.getenv("GITHUB_REPOSITORY")
    if not token or not repository:
        return 0, {"reason": "GITHUB_TOKEN or GITHUB_REPOSITORY not configured"}

    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}{path}",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {"reason": body}
        return exc.code, data
    except Exception as exc:  # pragma: no cover - network depends on GitHub runtime.
        return 0, {"reason": str(exc)}


def ensure_label(name: str, color: str, description: str) -> dict:
    payload = {"name": name, "color": color, "description": description}
    status, data = github_request("POST", "/labels", payload)
    if status in (200, 201):
        return {"label": name, "ok": True, "action": "created"}
    if status == 422:
        update_status, update_data = github_request("PATCH", f"/labels/{name}", payload)
        return {
            "label": name,
            "ok": update_status in (200, 201),
            "action": "updated" if update_status in (200, 201) else "update_failed",
            "details": update_data,
        }
    return {"label": name, "ok": False, "action": "create_failed", "details": data}


def ensure_labels() -> dict:
    results = [ensure_label(name, **settings) for name, settings in LABELS.items()]
    return {"ok": all(item["ok"] for item in results), "results": results}


def main() -> None:
    result = ensure_labels()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
