from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
REPORT_JSON = BACKEND / "reports" / "system_integrity.json"
REPORT_MD = BACKEND / "reports" / "system_integrity.md"


REQUIRED_DIRS = [
    "backend/memory",
    "backend/reports",
    "backend/comm/outbox",
    "backend/workflows",
    "backend/services",
    "backend/integrations",
    "apps/decision-hub/public",
    "apps/desktop-cloud-os/src",
    ".github/workflows",
]

REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    ".github/workflows/cloud_acceptance.yml",
    ".github/workflows/watchdog.yml",
    ".github/workflows/codex_autonomous_repair.yml",
    "backend/services/audit_service.py",
    "backend/services/evidence_verification_service.py",
    "backend/services/industry_war_room_service.py",
    "backend/services/intelligence_center_service.py",
    "backend/services/knowledge_benchmark_service.py",
    "backend/services/mission_control_service.py",
    "backend/services/project_action_board_service.py",
    "backend/services/project_intelligence_service.py",
    "backend/services/self_improvement_service.py",
    "backend/services/social_communication_service.py",
    "backend/services/team_execution_service.py",
    "backend/services/team_response_service.py",
    "backend/services/war_room_execution_queue_service.py",
    "backend/comm/chat_gateway.py",
    "backend/integrations/n8n_connector.py",
    "apps/desktop-cloud-os/scripts/prepare-resources.js",
]

SECRET_PATTERNS = [
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xoxb-[A-Za-z0-9-]{20,}"),
    re.compile(r"BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY"),
]


def write_text_if_missing(path: Path, text: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def check_secret_leaks() -> dict:
    scanned = 0
    hits: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", "node_modules", "dist", "work", "__pycache__"} for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".ico", ".zip", ".exe", ".msi"}:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            hits.append(path.relative_to(ROOT).as_posix())
    return {"ok": not hits, "scanned": scanned, "hits": hits}


def run_integrity_check(auto_fix: bool = True) -> dict:
    repairs: list[str] = []
    checks: list[dict] = []

    for relative in REQUIRED_DIRS:
        path = ROOT / relative
        ok = path.is_dir()
        if not ok and auto_fix:
            path.mkdir(parents=True, exist_ok=True)
            repairs.append(f"created directory {relative}")
            ok = True
        checks.append({"name": f"dir:{relative}", "ok": ok})

    for relative in REQUIRED_FILES:
        checks.append({"name": f"file:{relative}", "ok": (ROOT / relative).is_file()})

    if auto_fix:
        if write_text_if_missing(BACKEND / "memory" / "audit.log", ""):
            repairs.append("created append-only audit log")
        if write_text_if_missing(BACKEND / "memory" / "lessons.md", "# Lessons\n\n"):
            repairs.append("created lessons file")
        if write_text_if_missing(BACKEND / "comm" / "outbox" / ".gitkeep", ""):
            repairs.append("created comm/outbox marker")
        (BACKEND / "memory" / "project_library").mkdir(parents=True, exist_ok=True)
        (BACKEND / "memory" / "intelligence").mkdir(parents=True, exist_ok=True)
        (BACKEND / "memory" / "knowledge_base").mkdir(parents=True, exist_ok=True)
        (BACKEND / "memory" / "benchmark").mkdir(parents=True, exist_ok=True)
        (BACKEND / "memory" / "action_boards").mkdir(parents=True, exist_ok=True)
        (BACKEND / "memory" / "evidence").mkdir(parents=True, exist_ok=True)
        (BACKEND / "memory" / "war_room").mkdir(parents=True, exist_ok=True)
        (BACKEND / "memory" / "war_room_execution").mkdir(parents=True, exist_ok=True)
        (BACKEND / "memory" / "mission_control").mkdir(parents=True, exist_ok=True)
        (BACKEND / "memory" / "self_improvement").mkdir(parents=True, exist_ok=True)
        (BACKEND / "memory" / "team_execution").mkdir(parents=True, exist_ok=True)
        (BACKEND / "memory" / "team_responses").mkdir(parents=True, exist_ok=True)

    secret_check = check_secret_leaks()
    checks.append({"name": "secret_scan:no_plaintext_tokens", "ok": secret_check["ok"], "evidence": secret_check})

    workflow_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in (ROOT / ".github" / "workflows").glob("*.yml"))
    checks.append({"name": "actions:uses_backend_workflows", "ok": "backend/workflows" in workflow_text})
    checks.append({"name": "n8n:approval_gate_documented", "ok": (BACKEND / "integrations" / "n8n_connector.py").is_file()})
    checks.append({"name": "audit:append_service_available", "ok": (BACKEND / "services" / "audit_service.py").is_file()})
    checks.append({"name": "evidence_verification:dossier_service_available", "ok": (BACKEND / "services" / "evidence_verification_service.py").is_file()})
    checks.append({"name": "industry_war_room:vertical_team_package_available", "ok": (BACKEND / "services" / "industry_war_room_service.py").is_file()})
    checks.append({"name": "intelligence_center:service_available", "ok": (BACKEND / "services" / "intelligence_center_service.py").is_file()})
    checks.append({"name": "knowledge_benchmark:service_available", "ok": (BACKEND / "services" / "knowledge_benchmark_service.py").is_file()})
    checks.append({"name": "mission_control:operating_brief_available", "ok": (BACKEND / "services" / "mission_control_service.py").is_file()})
    checks.append({"name": "project_action_board:execution_board_available", "ok": (BACKEND / "services" / "project_action_board_service.py").is_file()})
    checks.append({"name": "project_intelligence:library_service_available", "ok": (BACKEND / "services" / "project_intelligence_service.py").is_file()})
    checks.append({"name": "self_improvement:service_available", "ok": (BACKEND / "services" / "self_improvement_service.py").is_file()})
    checks.append({"name": "social_communication:approval_gate_available", "ok": (BACKEND / "services" / "social_communication_service.py").is_file()})
    checks.append({"name": "team_execution:project_team_os_available", "ok": (BACKEND / "services" / "team_execution_service.py").is_file()})
    checks.append({"name": "team_response:team_answer_pack_available", "ok": (BACKEND / "services" / "team_response_service.py").is_file()})
    checks.append({"name": "war_room_execution:queue_service_available", "ok": (BACKEND / "services" / "war_room_execution_queue_service.py").is_file()})

    result = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ok": all(item["ok"] for item in checks),
        "auto_fix": auto_fix,
        "repairs": repairs,
        "checks": checks,
    }
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(render_report(result), encoding="utf-8")
    return result


def render_report(result: dict) -> str:
    lines = [
        "# v11 System Integrity Report",
        "",
        f"- Status: {'PASS' if result['ok'] else 'ATTENTION'}",
        f"- Generated: {result['created_at']}",
        f"- Auto fix: {result['auto_fix']}",
        "",
        "## Repairs",
        "",
    ]
    lines.extend(f"- {item}" for item in result["repairs"] or ["No low-risk repair needed."])
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- {'PASS' if item['ok'] else 'FAIL'} {item['name']}" for item in result["checks"])
    return "\n".join(lines) + "\n"


def main() -> None:
    result = run_integrity_check(auto_fix=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
