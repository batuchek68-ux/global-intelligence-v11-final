from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.audit_service import append_audit
from backend.services.evidence_verification_service import build_evidence_dossier
from backend.services.intelligence_center_service import build_intelligence_search_system, build_video_production_center
from backend.services.knowledge_benchmark_service import score_answer
from backend.services.project_action_board_service import build_action_board
from backend.services.project_intelligence_service import build_project_pipeline
from backend.services.search_service import multi_source_search
from backend.services.team_response_service import build_team_response_pack
from backend.services.war_room_execution_queue_service import (
    build_and_write_war_room_execution_queue,
    build_war_room_execution_queue,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
WAR_ROOM_MEMORY_DIR = BACKEND_ROOT / "memory" / "war_room"
WAR_ROOM_REPORT_DIR = BACKEND_ROOT / "reports" / "war_room"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _stable_id(*parts: str) -> str:
    raw = "|".join(str(part).strip().lower() for part in parts if part)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _memory_dir() -> Path:
    override = os.getenv("V11_WAR_ROOM_MEMORY_DIR")
    return Path(override) if override else WAR_ROOM_MEMORY_DIR


def _report_dir() -> Path:
    override = os.getenv("V11_WAR_ROOM_REPORT_DIR")
    return Path(override) if override else WAR_ROOM_REPORT_DIR


def _as_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or fallback
    if isinstance(value, str) and value.strip():
        parts = [item.strip() for item in value.split(",") if item.strip()]
        return parts or [value.strip()]
    return fallback


def _detect_country(text: str, metadata: dict[str, Any]) -> str:
    if metadata.get("country"):
        return str(metadata["country"]).strip()
    lower = text.lower()
    if "uzbekistan" in lower:
        return "Uzbekistan"
    if "kyrgyzstan" in lower:
        return "Kyrgyzstan"
    if "indonesia" in lower:
        return "Indonesia"
    if "russia" in lower:
        return "Russia"
    return "Kazakhstan"


def _executive_synthesis(
    objective: str,
    search_result: dict[str, Any],
    evidence_dossier: dict[str, Any],
    project_pipeline: dict[str, Any],
    team_pack: dict[str, Any],
) -> str:
    confirmation_gate = search_result.get("project_confirmation_gate", {})
    promotion = project_pipeline.get("promotion_readiness", {})
    evidence_status = evidence_dossier.get("verification_status", "missing")
    confidence = evidence_dossier.get("confidence", 0)
    return "\n".join(
        [
            "DRAFT - internal operating synthesis, not approved for external sending",
            f"Objective: {objective}",
            f"Evidence status: {evidence_status}; confidence={confidence}; official_sources={evidence_dossier.get('summary', {}).get('official_sources', 0)}.",
            f"Search confirmation gate: {confirmation_gate.get('status', 'missing')}; confirmed_project_allowed={confirmation_gate.get('can_create_confirmed_project_record')}.",
            f"Promotion readiness: {promotion.get('status', 'missing')}; internal_draft={promotion.get('can_generate_internal_promotion_draft')}; external_use={promotion.get('approved_for_external_use')}.",
            f"Team answer quality: {team_pack.get('quality_score', {}).get('overall_score', 0)}.",
            "Decision: treat unverified material as leads only. Build official evidence first, then project record, then internal promotion draft, then human approval before any external action.",
        ]
    )


def build_industry_war_room(
    objective: str,
    *,
    country: str | None = None,
    industries: list[str] | str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    audience: str = "internal",
    persist: bool = True,
) -> dict[str, Any]:
    """Build a vertical-industry operating package rather than a generic answer."""
    objective = objective.strip()
    if not objective:
        raise ValueError("objective is required")
    evidence_items = evidence or []
    metadata = {"country": country or _detect_country(objective, {}), "industries": industries or ["infrastructure", "logistics", "energy"]}
    country_name = str(country or _detect_country(objective, metadata))
    industry_list = _as_list(industries, ["infrastructure", "logistics", "energy"])
    room_id = _stable_id(objective, country_name, ",".join(industry_list), _today_key())

    search_result = multi_source_search(objective)
    evidence_dossier = build_evidence_dossier(objective, evidence_items, project=objective, country=country_name)
    project_pipeline = build_project_pipeline(objective, country_name, evidence_items, persist=persist and bool(evidence_items))
    intelligence_system = build_intelligence_search_system([objective], [country_name], industry_list)
    video_center = build_video_production_center([objective], [country_name], industry_list[:2])
    team_result = build_team_response_pack(
        objective,
        metadata={"country": country_name, "industries": industry_list, "audience": audience},
        evidence=evidence_items,
        persist=persist,
    )
    team_pack = team_result.get("pack", team_result)
    action_board = build_action_board(
        {
            "created_at": _now_iso(),
            "project": {
                "title": objective[:120],
                "country": country_name,
                "stage": project_pipeline.get("project", {}).get("category", "war_room"),
                "next_decision": "Approve outreach only after official evidence and risk review.",
            },
            "classification": {
                "is_major_matter": evidence_dossier.get("requires_human_review", True)
                or project_pipeline.get("promotion_readiness", {}).get("approved_for_external_use") is not True
            },
            "judgment": {
                "level": "high" if evidence_dossier.get("requires_human_review", True) else "medium",
                "score": max(60, 100 - int(evidence_dossier.get("confidence", 0) or 0)),
                "triggers": evidence_dossier.get("high_risk_terms", []) or ["project_confirmation", "promotion_approval"],
            },
        },
        evidence_dossier,
    )
    synthesis = _executive_synthesis(objective, search_result, evidence_dossier, project_pipeline, team_pack)
    quality_score = score_answer(
        objective,
        synthesis + "\n" + str(team_pack.get("executive_answer", "")),
        evidence=evidence_items,
    )
    room = {
        "ok": True,
        "id": room_id,
        "created_at": _now_iso(),
        "mode": "industry_war_room",
        "objective": objective,
        "country": country_name,
        "industries": industry_list,
        "audience": audience,
        "executive_synthesis": synthesis,
        "search_confirmation": {
            "source_readiness": search_result.get("source_readiness", {}),
            "project_confirmation_gate": search_result.get("project_confirmation_gate", {}),
            "priority_queries": search_result.get("project_search_plan", [])[:12],
        },
        "evidence": {
            "verification_status": evidence_dossier.get("verification_status"),
            "confidence": evidence_dossier.get("confidence"),
            "summary": evidence_dossier.get("summary"),
            "blocked_actions": evidence_dossier.get("blocked_actions", []),
        },
        "project_execution": {
            "project": project_pipeline.get("project"),
            "promotion_readiness": project_pipeline.get("promotion_readiness"),
            "project_library": project_pipeline.get("project_library"),
            "next_actions": project_pipeline.get("next_actions", []),
            "blocked_actions": project_pipeline.get("blocked_actions", []),
        },
        "team": {
            "mode": team_pack.get("mode"),
            "roles": team_pack.get("team_roles", []),
            "quality_score": team_pack.get("quality_score", {}),
            "approval_boundary": team_pack.get("approval_boundary", {}),
        },
        "intelligence_system": {
            "categories": [
                {
                    "id": item.get("id"),
                    "label": item.get("label"),
                    "first_search_term": item.get("search_terms", [""])[0] if item.get("search_terms") else "",
                    "tracking_frequency": item.get("tracking_frequency"),
                }
                for item in intelligence_system.get("categories", [])
            ],
            "source_groups": intelligence_system.get("source_groups", {}),
        },
        "video_center": {
            "video_keywords": video_center.get("video_keywords", [])[:12],
            "platform_searches": video_center.get("platform_searches", [])[:12],
            "script_templates": video_center.get("script_templates", []),
            "rules": video_center.get("rules", []),
        },
        "action_board": {
            "risk_gate": action_board.get("risk_gate"),
            "summary": action_board.get("summary"),
            "tasks": action_board.get("tasks", []),
        },
        "quality_score": quality_score,
        "approval_boundary": {
            "draft_only": True,
            "external_use_allowed": False,
            "human_approval_required": True,
            "blocked_actions": sorted(
                set(evidence_dossier.get("blocked_actions", []) + project_pipeline.get("blocked_actions", []))
            ),
        },
        "operating_rule": "v11 works as a vertical industry project team: evidence, search verification, execution, media draft, score, and approval gate in one package.",
    }
    execution_queue = build_war_room_execution_queue(room)
    room["execution_queue"] = {
        "id": execution_queue["id"],
        "summary": execution_queue["summary"],
        "tasks": execution_queue["tasks"][:12],
        "rules": execution_queue["rules"],
    }
    if persist:
        result = write_industry_war_room(room)
        queue_result = build_and_write_war_room_execution_queue(room)
        result["execution_queue_path"] = queue_result["json_path"]
        result["execution_queue_report_path"] = queue_result["report_path"]
        return result
    return {"ok": True, "war_room": room}


def render_industry_war_room(room: dict[str, Any]) -> str:
    lines = [
        f"# v11 Industry War Room: {room.get('objective')}",
        "",
        "DRAFT - internal operating package, not approved for external sending",
        "",
        "## Executive Synthesis",
        "",
        room.get("executive_synthesis", ""),
        "",
        "## Search Confirmation",
        "",
        f"- Gate: {room.get('search_confirmation', {}).get('project_confirmation_gate', {}).get('status')}",
        f"- Confirmed project allowed: {room.get('search_confirmation', {}).get('project_confirmation_gate', {}).get('can_create_confirmed_project_record')}",
        "",
        "## Project Execution",
        "",
        f"- Promotion readiness: {room.get('project_execution', {}).get('promotion_readiness', {}).get('status')}",
        f"- External use approved: {room.get('project_execution', {}).get('promotion_readiness', {}).get('approved_for_external_use')}",
        "",
        "## Team Roles",
        "",
    ]
    for role in room.get("team", {}).get("roles", []):
        lines.append(f"- {role.get('role')}: {role.get('next_step')}")
    lines.extend(["", "## Action Board", ""])
    for task in room.get("action_board", {}).get("tasks", [])[:12]:
        lines.append(f"- {task.get('owner')}: {task.get('task')} [{task.get('status')}]")
    lines.extend(["", "## Execution Queue", ""])
    queue_summary = room.get("execution_queue", {}).get("summary", {})
    lines.append(
        f"- Tasks: {queue_summary.get('task_count', 0)}; "
        f"open={queue_summary.get('open_count', 0)}; "
        f"blocked={queue_summary.get('blocked_count', 0)}; "
        f"approval={queue_summary.get('approval_required_count', 0)}"
    )
    for item in room.get("execution_queue", {}).get("tasks", [])[:12]:
        lines.append(f"- {item.get('id')}: {item.get('role')} | {item.get('status')} | {item.get('task')}")
    lines.extend(["", "## Video Center", ""])
    for item in room.get("video_center", {}).get("platform_searches", [])[:8]:
        lines.append(f"- {item.get('platform')}: {item.get('keyword')}")
    lines.extend(["", "## Quality", ""])
    lines.append(f"- Overall score: {room.get('quality_score', {}).get('overall_score')}")
    lines.extend(["", "## Approval Boundary", ""])
    boundary = room.get("approval_boundary", {})
    lines.append(f"- Human approval required: {boundary.get('human_approval_required')}")
    for blocked in boundary.get("blocked_actions", [])[:12]:
        lines.append(f"- Blocked: {blocked}")
    lines.append("")
    return "\n".join(lines)


def write_industry_war_room(room: dict[str, Any]) -> dict[str, Any]:
    memory_dir = _memory_dir()
    report_dir = _report_dir()
    memory_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = memory_dir / f"{room['id']}.json"
    md_path = report_dir / f"{room['id']}.md"
    latest_json = memory_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    json_text = json.dumps(room, ensure_ascii=False, indent=2)
    md_text = render_industry_war_room(room)
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    append_audit(
        "INDUSTRY_WAR_ROOM_BUILT",
        "DONE",
        f"Built v11 industry war room id={room['id']} objective={room['objective'][:120]}; external use blocked.",
        confidence=95,
        risk="MEDIUM",
    )
    return {"ok": True, "war_room": room, "json_path": str(json_path), "report_path": str(md_path)}
