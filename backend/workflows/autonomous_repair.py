from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
REPORT_JSON = ROOT / "reports" / "autonomous_repair.json"
REPORT_MD = ROOT / "reports" / "autonomous_repair.md"
REPORT_MD_RELATIVE = "reports/autonomous_repair.md"
PYTHON_COMMAND_HINT = "python backend/workflows/autonomous_repair.py"


def run_step(name: str, command: list[str], cwd: Path = ROOT) -> dict:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return {
        "name": name,
        "command": command,
        "cwd": str(cwd),
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def diagnose(steps: list[dict]) -> list[str]:
    findings: list[str] = []
    for step in steps:
        if step["ok"]:
            continue
        text = f"{step.get('stdout_tail', '')}\n{step.get('stderr_tail', '')}".lower()
        if "preflight" in step["name"].lower():
            findings.append("Repository shape or required operating files are incomplete.")
        elif "unittest" in " ".join(step["command"]):
            findings.append("Unit tests failed; review stderr tail and repair code before cloud acceptance.")
        elif "cloud_acceptance" in " ".join(step["command"]):
            findings.append("Cloud acceptance evidence is incomplete; run daily_job/watchdog and persist state.")
        if "syntaxerror" in text:
            findings.append("Python syntax error detected.")
        if "modulenotfounderror" in text:
            findings.append("Python import/module path error detected.")
    if not findings:
        findings.append("No repair needed. All autonomous checks passed.")
    return findings


def render_report(result: dict) -> str:
    lines = [
        "# Codex / AI Autonomous Repair Report",
        "",
        f"- Status: {'PASS' if result['ok'] else 'ATTENTION'}",
        f"- Generated: {result['created_at']}",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {item}" for item in result["findings"])
    lines.extend(["", "## Steps", ""])
    for step in result["steps"]:
        lines.append(f"- {'PASS' if step['ok'] else 'FAIL'} `{step['name']}`: `{ ' '.join(step['command']) }`")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This workflow may diagnose and prepare repair evidence automatically. It must not publish externally, sign, pay, or commit customer promises without owner approval.",
            "",
        ]
    )
    return "\n".join(lines)


def run_autonomous_repair() -> dict:
    steps = [
        run_step("v11 system integrity self-check and low-risk repair", [sys.executable, "workflows/system_integrity.py"]),
        run_step("preflight", [sys.executable, "workflows/preflight_check.py"]),
        run_step("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=REPO_ROOT),
        run_step("daily operating cycle", [sys.executable, "workflows/daily_job.py"]),
        run_step("watchdog", [sys.executable, "workflows/watchdog.py"]),
        run_step("cloud acceptance", [sys.executable, "workflows/cloud_acceptance.py"]),
    ]
    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ok": all(step["ok"] for step in steps),
        "steps": steps,
        "findings": diagnose(steps),
        "boundary": "Codex may self-fix low-risk framework/program/config/test issues. External replies, publishing, payment, contract, quote, and customer commitments require human approval.",
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_report(result), encoding="utf-8")
    return result


def main() -> None:
    result = run_autonomous_repair()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
