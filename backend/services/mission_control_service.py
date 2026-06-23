from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.audit_service import append_audit
from backend.services.project_intelligence_service import assess_promotion_readiness, read_project_library
from backend.services.search_service import multi_source_search


BACKEND_ROOT = Path(__file__).resolve().parents[1]
MISSION_DIR = BACKEND_ROOT / "reports" / "mission_control"
MISSION_MEMORY_DIR = BACKEND_ROOT / "memory" / "mission_control"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mission_dir() -> Path:
    override = os.getenv("V11_MISSION_CONTROL_DIR")
    return Path(override) if override else MISSION_DIR


def _mission_memory_dir() -> Path:
    override = os.getenv("V11_MISSION_CONTROL_MEMORY_DIR")
    return Path(override) if override else MISSION_MEMORY_DIR


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.is_dir():
        return None
    files = sorted(directory.glob(pattern), key=lambda item: item.stat().st_mtime, reverse=True)
    return files[0] if files else None


def build_mission_control_snapshot(root: Path | None = None) -> dict[str, Any]:
    base = root or BACKEND_ROOT
    last_run = _read_json(base / "memory" / "last_run.json", {})
    knowledge = _read_json(base / "memory" / "knowledge_base" / "industry_knowledge.json", {})
    benchmark = _read_json(base / "memory" / "benchmark" / "v11_benchmark_50.json", {})
    answer_score = _read_json(base / "reports" / "benchmark" / "daily_answer_score.json", {})
    latest_evidence = _read_json(base / "memory" / "evidence" / "latest.json", {})
    latest_action_board = _read_json(base / "memory" / "action_boards" / "latest.json", {})
    latest_team_response = _read_json(base / "memory" / "team_responses" / "latest.json", {})
    latest_war_room = _read_json(base / "memory" / "war_room" / "latest.json", {})
    latest_war_room_queue = _read_json(base / "memory" / "war_room_execution" / "latest.json", {})
    keyword_bank = _read_json(base / "memory" / "intelligence" / "keyword_bank.json", {})
    owner_inbox = _read_text(base / "reports" / "owner_inbox.md")
    latest_brief = _latest_file(base / "reports" / "intelligence_briefs", "*.md")
    latest_video = _latest_file(base / "reports" / "video_center", "*.json")
    team_reports = sorted((base / "reports" / "team_execution").glob("*.md")) if (base / "reports" / "team_execution").is_dir() else []
    evidence_files = sorted((base / "memory" / "evidence").glob("*.json")) if (base / "memory" / "evidence").is_dir() else []
    action_board_files = sorted((base / "memory" / "action_boards").glob("*.json")) if (base / "memory" / "action_boards").is_dir() else []
    team_response_files = sorted((base / "memory" / "team_responses").glob("*.json")) if (base / "memory" / "team_responses").is_dir() else []
    war_room_files = sorted((base / "memory" / "war_room").glob("*.json")) if (base / "memory" / "war_room").is_dir() else []
    war_room_queue_files = sorted((base / "memory" / "war_room_execution").glob("*.json")) if (base / "memory" / "war_room_execution").is_dir() else []
    project_library = read_project_library(base / "memory" / "project_library" / "projects.json")
    project_library_summary = project_library.get("summary", {})
    search_gate_sample = multi_source_search("Kazakhstan engineering trade customs investment promotion video")
    project_confirmation_gate = search_gate_sample.get("project_confirmation_gate", {})
    source_readiness = search_gate_sample.get("source_readiness", {})
    weak_promotion_gate = assess_promotion_readiness(
        {
            "confirmation_level": "unverified_or_secondary",
            "confidence": 55,
            "category": "unknown",
            "government_sources": [],
            "owner_candidates": [],
            "developer_candidates": [],
        }
    )
    official_promotion_gate = assess_promotion_readiness(
        {
            "confirmation_level": "government_confirmed",
            "confidence": 95,
            "category": "planned",
            "government_sources": [{"url": "https://www.gov.kz/demo"}],
            "owner_candidates": ["Official owner candidate"],
            "developer_candidates": ["Official developer candidate"],
        }
    )

    cases = last_run.get("cases", [])
    waiting_cases = [
        case for case in cases
        if case.get("classification", {}).get("is_major_matter") and not case.get("owner_decision")
    ]
    autonomous_cases = [
        case for case in cases
        if not case.get("classification", {}).get("is_major_matter")
    ]
    top_keywords = [item.get("keyword") for item in keyword_bank.get("keywords", [])[:12] if item.get("keyword")]

    snapshot = {
        "ok": True,
        "created_at": _now_iso(),
        "status": "human_review_required" if waiting_cases else "operating",
        "mission": "vertical industry intelligence brain plus verified search plus project execution system",
        "command_center": {
            "project_count": last_run.get("project_count", 0),
            "case_count": last_run.get("case_count", 0),
            "major_matter_count": last_run.get("major_matter_count", 0),
            "waiting_for_owner": len(waiting_cases),
            "autonomous_cases": len(autonomous_cases),
        },
        "capability_evidence": {
            "knowledge_domains": len(knowledge.get("domains", {})),
            "customs_information_domain": "customs_information" in knowledge.get("domains", {}),
            "benchmark_questions": benchmark.get("question_count", 0),
            "answer_score": answer_score.get("overall_score", 0),
            "answer_score_verdict": answer_score.get("verdict", "missing"),
            "intelligence_keywords": len(keyword_bank.get("keywords", [])),
            "latest_intelligence_brief": str(latest_brief) if latest_brief else None,
            "latest_video_center": str(latest_video) if latest_video else None,
            "team_execution_reports": len(team_reports),
            "evidence_dossiers": len([item for item in evidence_files if item.name != "latest.json"]),
            "latest_evidence_status": latest_evidence.get("verification_status", "missing"),
            "latest_evidence_confidence": latest_evidence.get("confidence", 0),
            "action_boards": len([item for item in action_board_files if item.name != "latest.json"]),
            "latest_action_board_status": latest_action_board.get("risk_gate", {}).get("status", "missing"),
            "latest_action_board_tasks": latest_action_board.get("summary", {}).get("task_count", 0),
            "team_responses": len([item for item in team_response_files if item.name != "latest.json"]),
            "latest_team_response_score": latest_team_response.get("quality_score", {}).get("overall_score", 0),
            "latest_team_response_mode": latest_team_response.get("mode", "missing"),
            "war_rooms": len([item for item in war_room_files if item.name != "latest.json"]),
            "latest_war_room_score": latest_war_room.get("quality_score", {}).get("overall_score", 0),
            "latest_war_room_mode": latest_war_room.get("mode", "missing"),
            "latest_war_room_roles": len(latest_war_room.get("team", {}).get("roles", [])),
            "latest_war_room_search_gate": latest_war_room.get("search_confirmation", {}).get("project_confirmation_gate", {}).get("status", "missing"),
            "latest_war_room_promotion_gate": latest_war_room.get("project_execution", {}).get("promotion_readiness", {}).get("status", "missing"),
            "latest_war_room_external_use": latest_war_room.get("approval_boundary", {}).get("external_use_allowed"),
            "war_room_execution_queues": len([item for item in war_room_queue_files if item.name != "latest.json"]),
            "latest_war_room_queue_mode": latest_war_room_queue.get("mode", "missing"),
            "latest_war_room_queue_tasks": latest_war_room_queue.get("summary", {}).get("task_count", 0),
            "latest_war_room_queue_open": latest_war_room_queue.get("summary", {}).get("open_count", 0),
            "latest_war_room_queue_blocked": latest_war_room_queue.get("summary", {}).get("blocked_count", 0),
            "latest_war_room_queue_approval": latest_war_room_queue.get("summary", {}).get("approval_required_count", 0),
            "search_source_readiness": {
                "configured_or_manual_sources": source_readiness.get("configured_count", 0),
                "manual_entry_sources": source_readiness.get("manual_entry_count", 0),
                "missing_configuration": len(source_readiness.get("missing_configuration", [])),
            },
            "search_confirmation_gate": {
                "status": project_confirmation_gate.get("status", "missing"),
                "can_create_confirmed_project_record": project_confirmation_gate.get("can_create_confirmed_project_record"),
                "required_query_groups": sorted(project_confirmation_gate.get("required_query_groups", {}).keys()),
                "blocked_actions": project_confirmation_gate.get("blocked_until_confirmed", []),
            },
            "project_library_summary": project_library_summary,
            "promotion_readiness_gate": {
                "weak_lead_status": weak_promotion_gate.get("status"),
                "official_project_status": official_promotion_gate.get("status"),
                "external_use_default": official_promotion_gate.get("approved_for_external_use"),
                "human_approval_required": official_promotion_gate.get("human_approval_required_for_external_use"),
                "blocked_actions": official_promotion_gate.get("blocked_actions", []),
            },
        },
        "priority_queue": [
            {
                "project": case.get("project", {}).get("title"),
                "country": case.get("project", {}).get("country"),
                "risk_level": case.get("judgment", {}).get("level"),
                "triggers": case.get("judgment", {}).get("triggers", []),
                "required_decision": case.get("project", {}).get("next_decision"),
                "blocked_actions": [
                    "external commitment",
                    "formal quotation",
                    "contract or payment approval",
                    "public publishing",
                ],
            }
            for case in waiting_cases
        ],
        "autonomous_work": [
            {
                "project": case.get("project", {}).get("title"),
                "status": case.get("execution", {}).get("status"),
                "result": case.get("execution", {}).get("result"),
            }
            for case in autonomous_cases[:10]
        ],
        "search_and_learning": {
            "top_keywords": top_keywords,
            "benchmark_targets": ["v11", "Doubao", "Yuanbao"],
            "scoring_dimensions": ["accuracy", "evidence", "actionability", "risk_judgment", "professional_depth"],
            "search_confirmation_rule": "Search output is a lead until official government, procurement, customs, regulator, or official company evidence is attached.",
            "promotion_readiness_rule": "Investment-promotion drafts are internal only; external use requires human approval even after official evidence.",
        },
        "owner_inbox_available": "Owner Inbox" in owner_inbox,
        "rules": [
            "This snapshot is internal operating evidence, not an external message.",
            "Government/customs/project facts require source verification before commitment.",
            "Formal replies, quotes, payments, contracts, and public posts require human approval.",
            "n8n can assist workflow routing but must not bypass v11 risk gates.",
        ],
    }
    return snapshot


def render_mission_control(snapshot: dict[str, Any]) -> str:
    command = snapshot.get("command_center", {})
    evidence = snapshot.get("capability_evidence", {})
    lines = [
        "# v11 Mission Control",
        "",
        "DRAFT - internal operating brief, not approved for external sending",
        "",
        f"- Status: {snapshot.get('status')}",
        f"- Created: {snapshot.get('created_at')}",
        f"- Mission: {snapshot.get('mission')}",
        "",
        "## Command Center",
        "",
        f"- Projects: {command.get('project_count', 0)}",
        f"- Cases: {command.get('case_count', 0)}",
        f"- Major matters: {command.get('major_matter_count', 0)}",
        f"- Waiting for owner: {command.get('waiting_for_owner', 0)}",
        f"- Autonomous cases: {command.get('autonomous_cases', 0)}",
        "",
        "## Capability Evidence",
        "",
        f"- Knowledge domains: {evidence.get('knowledge_domains', 0)}",
        f"- Customs information domain: {evidence.get('customs_information_domain')}",
        f"- Benchmark questions: {evidence.get('benchmark_questions', 0)}",
        f"- Answer score: {evidence.get('answer_score', 0)} ({evidence.get('answer_score_verdict')})",
        f"- Intelligence keywords: {evidence.get('intelligence_keywords', 0)}",
        f"- Team execution reports: {evidence.get('team_execution_reports', 0)}",
        f"- Evidence dossiers: {evidence.get('evidence_dossiers', 0)}",
        f"- Latest evidence status: {evidence.get('latest_evidence_status', 'missing')} ({evidence.get('latest_evidence_confidence', 0)})",
        f"- Action boards: {evidence.get('action_boards', 0)}",
        f"- Latest action board: {evidence.get('latest_action_board_status', 'missing')} ({evidence.get('latest_action_board_tasks', 0)} tasks)",
        f"- Team responses: {evidence.get('team_responses', 0)}",
        f"- Latest team response score: {evidence.get('latest_team_response_score', 0)}",
        f"- War rooms: {evidence.get('war_rooms', 0)}",
        f"- Latest war room: score={evidence.get('latest_war_room_score', 0)}, roles={evidence.get('latest_war_room_roles', 0)}, search={evidence.get('latest_war_room_search_gate', 'missing')}, promotion={evidence.get('latest_war_room_promotion_gate', 'missing')}",
        f"- War room execution queues: {evidence.get('war_room_execution_queues', 0)}",
        f"- Latest execution queue: tasks={evidence.get('latest_war_room_queue_tasks', 0)}, open={evidence.get('latest_war_room_queue_open', 0)}, blocked={evidence.get('latest_war_room_queue_blocked', 0)}, approval={evidence.get('latest_war_room_queue_approval', 0)}",
        f"- Search confirmation gate: {evidence.get('search_confirmation_gate', {}).get('status', 'missing')}",
        f"- Search manual/source entries: {evidence.get('search_source_readiness', {}).get('configured_or_manual_sources', 0)}",
        f"- Project promotion gate: weak={evidence.get('promotion_readiness_gate', {}).get('weak_lead_status', 'missing')}, official={evidence.get('promotion_readiness_gate', {}).get('official_project_status', 'missing')}",
        f"- Project library promotion-ready drafts: {evidence.get('project_library_summary', {}).get('promotion_draft_ready', 0)}",
        "",
        "## Priority Queue",
        "",
    ]
    priority = snapshot.get("priority_queue", [])
    if priority:
        for item in priority:
            lines.append(f"- {item.get('project')} | {item.get('country')} | risk={item.get('risk_level')} | decision={item.get('required_decision')}")
    else:
        lines.append("- No major matter waiting for owner decision.")
    lines.extend(["", "## Autonomous Work", ""])
    autonomous = snapshot.get("autonomous_work", [])
    if autonomous:
        for item in autonomous:
            lines.append(f"- {item.get('project')} | {item.get('status')} | {item.get('result')}")
    else:
        lines.append("- No autonomous cases recorded in the latest run.")
    lines.extend(["", "## Search And Learning", ""])
    for keyword in snapshot.get("search_and_learning", {}).get("top_keywords", [])[:10]:
        lines.append(f"- {keyword}")
    lines.extend(["", "## Rules", ""])
    lines.extend(f"- {rule}" for rule in snapshot.get("rules", []))
    lines.append("")
    return "\n".join(lines)


def write_mission_control(root: Path | None = None) -> dict[str, Any]:
    snapshot = build_mission_control_snapshot(root)
    report_dir = _mission_dir()
    memory_dir = _mission_memory_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    memory_dir.mkdir(parents=True, exist_ok=True)
    json_path = memory_dir / "latest.json"
    md_path = report_dir / "latest.md"
    json_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_mission_control(snapshot), encoding="utf-8")
    append_audit(
        "MISSION_CONTROL_SNAPSHOT",
        "DONE",
        "Built internal v11 mission control snapshot for project execution, benchmark, knowledge, search, video, and approval queue.",
        confidence=92,
        risk="LOW",
    )
    return {"ok": True, "snapshot": snapshot, "json_path": str(json_path), "report_path": str(md_path)}
