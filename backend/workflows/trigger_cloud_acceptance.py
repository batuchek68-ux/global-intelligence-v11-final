from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REPORT_RELATIVE = "reports/cloud_acceptance_remote.json"
REPORT = ROOT / REPORT_RELATIVE
WORKFLOW_FILE = "cloud_acceptance.yml"
TRANSIENT_ERROR_MARKERS = (
    "UNEXPECTED_EOF_WHILE_READING",
    "timed out",
    "WinError 10054",
    "Remote end closed connection",
    "Connection reset",
)

from workflows.cloud_config import configured_repository, configured_token


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def github_request(
    method: str,
    repository: str,
    path: str,
    token: str,
    payload: dict | None = None,
) -> tuple[int, dict | list | str | None]:
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    for attempt in range(1, 4):
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repository}{path}",
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
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            try:
                parsed: dict | list | str = json.loads(body) if body else {}
            except json.JSONDecodeError:
                parsed = body
            return exc.code, parsed
        except Exception as exc:
            detail = str(exc)
            if attempt < 3 and any(marker in detail for marker in TRANSIENT_ERROR_MARKERS):
                time.sleep(attempt * 2)
                continue
            return 0, {"message": detail, "stage": "network_error"}

    return 0, {"message": "GitHub request failed after retries.", "stage": "network_error"}


def get_workflow(repository: str, token: str) -> dict:
    status, data = github_request("GET", repository, f"/actions/workflows/{WORKFLOW_FILE}", token)
    return {"ok": status == 200, "status": status, "data": data}


def dispatch_workflow(repository: str, token: str, ref: str) -> dict:
    payload = {"ref": ref}
    status, data = github_request(
        "POST",
        repository,
        f"/actions/workflows/{WORKFLOW_FILE}/dispatches",
        token,
        payload,
    )
    return {"ok": status == 204, "status": status, "data": data, "ref": ref}


def list_runs(repository: str, token: str) -> dict:
    query = urllib.parse.urlencode({"event": "workflow_dispatch", "per_page": 10})
    status, data = github_request(
        "GET",
        repository,
        f"/actions/workflows/{WORKFLOW_FILE}/runs?{query}",
        token,
    )
    return {"ok": status == 200, "status": status, "data": data}


def find_new_run(repository: str, token: str, started_after: str) -> dict | None:
    runs_result = list_runs(repository, token)
    if not runs_result["ok"]:
        return None
    runs = []
    data = runs_result["data"]
    if isinstance(data, dict):
        runs = data.get("workflow_runs", [])
    for run in runs:
        if run.get("created_at", "") >= started_after:
            return run
    return runs[0] if runs else None


def get_run(repository: str, token: str, run_id: int) -> dict:
    status, data = github_request("GET", repository, f"/actions/runs/{run_id}", token)
    return {"ok": status == 200, "status": status, "data": data}


def get_run_jobs(repository: str, token: str, run_id: int) -> dict:
    status, data = github_request("GET", repository, f"/actions/runs/{run_id}/jobs", token)
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    failed_steps = []
    for job in jobs:
        for step in job.get("steps", []):
            if step.get("conclusion") == "failure":
                failed_steps.append(
                    {
                        "job": job.get("name"),
                        "step": step.get("name"),
                        "number": step.get("number"),
                        "status": step.get("status"),
                        "conclusion": step.get("conclusion"),
                    }
                )
    return {
        "ok": status == 200,
        "status": status,
        "jobs": [
            {
                "name": job.get("name"),
                "status": job.get("status"),
                "conclusion": job.get("conclusion"),
                "html_url": job.get("html_url"),
            }
            for job in jobs
        ],
        "failed_steps": failed_steps,
        "details": data if status != 200 else None,
    }


def wait_for_run(repository: str, token: str, run_id: int, timeout_seconds: int, interval_seconds: int) -> dict:
    deadline = time.time() + timeout_seconds
    latest: dict = {}
    while time.time() < deadline:
        result = get_run(repository, token, run_id)
        if result["ok"] and isinstance(result["data"], dict):
            latest = result["data"]
            if latest.get("status") == "completed":
                return {"ok": True, "timed_out": False, "run": latest}
        time.sleep(interval_seconds)
    return {"ok": False, "timed_out": True, "run": latest}


def trigger_cloud_acceptance(
    repository: str,
    token: str,
    ref: str = "main",
    wait: bool = True,
    timeout_seconds: int = 900,
    interval_seconds: int = 10,
) -> dict:
    started_at = now_iso().replace("+00:00", "Z")
    workflow = get_workflow(repository, token)
    if not workflow["ok"]:
        return {
            "ok": False,
            "stage": "workflow_lookup",
            "repository": repository,
            "workflow": WORKFLOW_FILE,
            "details": workflow,
        }

    dispatch = dispatch_workflow(repository, token, ref)
    if not dispatch["ok"]:
        return {
            "ok": False,
            "stage": "workflow_dispatch",
            "repository": repository,
            "workflow": WORKFLOW_FILE,
            "details": dispatch,
        }

    run = None
    for _ in range(12):
        run = find_new_run(repository, token, started_at)
        if run:
            break
        time.sleep(5)

    if not run:
        return {
            "ok": False,
            "stage": "run_lookup",
            "repository": repository,
            "workflow": WORKFLOW_FILE,
            "dispatch": dispatch,
            "reason": "workflow dispatched but run was not found yet",
        }

    run_id = int(run["id"])
    result = {
        "ok": True,
        "stage": "dispatched",
        "repository": repository,
        "workflow": WORKFLOW_FILE,
        "run_id": run_id,
        "run_url": run.get("html_url"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "ref": ref,
        "created_at": run.get("created_at"),
    }
    if wait:
        waited = wait_for_run(repository, token, run_id, timeout_seconds, interval_seconds)
        final_run = waited.get("run", {})
        result.update(
            {
                "ok": waited.get("ok") and final_run.get("conclusion") == "success",
                "stage": "completed" if waited.get("ok") else "waiting",
                "timed_out": waited.get("timed_out"),
                "status": final_run.get("status"),
                "conclusion": final_run.get("conclusion"),
                "run_url": final_run.get("html_url", result.get("run_url")),
            }
        )
        if final_run.get("status") == "completed":
            result["jobs"] = get_run_jobs(repository, token, run_id)
    return result


def write_report(result: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trigger GitHub Cloud Acceptance via the GitHub REST API.")
    parser.add_argument("--repository", default=configured_repository(os.getenv("GITHUB_REPOSITORY")), help="GitHub repository as owner/name.")
    parser.add_argument("--ref", default=os.getenv("GITHUB_REF_NAME", "main"), help="Git ref to run, default main.")
    parser.add_argument("--no-wait", action="store_true", help="Dispatch only; do not wait for completion.")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--interval-seconds", type=int, default=10)
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

    result = trigger_cloud_acceptance(
        repository=args.repository,
        token=token,
        ref=args.ref,
        wait=not args.no_wait,
        timeout_seconds=args.timeout_seconds,
        interval_seconds=args.interval_seconds,
    )
    write_report(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
