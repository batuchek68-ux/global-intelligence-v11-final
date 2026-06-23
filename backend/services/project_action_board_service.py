from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.audit_service import append_audit


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ACTION_MEMORY_DIR = BACKEND_ROOT / "memory" / "action_boards"
ACTION_REPORT_DIR = BACKEND_ROOT / "reports" / "action_boards"

ROLE_LABELS = {
    "trade_lead": "International trade lead",
    "research_analyst": "Research intelligence analyst",
    "investment_promotion_lead": "Investment promotion lead",
    "video_media_producer": "Video and media producer",
    "project_manager": "Project execution manager",
    "risk_approval_officer": "Risk and approval officer",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory_dir() -> Path:
    override = os.getenv("V11_ACTION_BOARD_MEMORY_DIR")
    return Path(override) if override else ACTION_MEMORY_DIR


def _report_dir() -> Path:
    override = os.getenv("V11_ACTION_BOARD_REPORT_DIR")
    return Path(override) if override else ACTION_REPORT_DIR


def _stable_id(*parts: str) -> str:
    raw = "|".join(str(part).strip().lower() for part in parts if part)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _risk_gate(case: dict[str, Any], evidence_dossier: dict[str, Any] | None) -> dict[str, Any]:
    classification = case.get("classification", {})
    judgment = case.get("judgment", {})
    needs_owner = bool(classification.get("is_major_matter")) and not case.get("owner_decision")
    evidence_review = bool(evidence_dossier and evidence_dossier.get("requires_human_review"))
    blocked = needs_owner or evidence_review
    return {
        "blocked": blocked,
        "status": "pending_owner" if needs_owner else ("evidence_review_required" if evidence_review else "open"),
        "risk_level": judgment.get("level", "unknown"),
        "risk_score": judgment.get("score", 0),
        "reasons": [
            *([f"major matter: {case.get('project', {}).get('next_decision', '')}"] if needs_owner else []),
            *([f"evidence status: {evidence_dossier.get('verification_status')}" ] if evidence_review and evidence_dossier else []),
        ],
        "blocked_actions": [
            "external commitment",
            "formal quotation",
            "contract or payment approval",
            "public publishing",
            "customer delivery promise",
        ] if blocked else [],
    }


def _task(task_id: str, role: str, title: str, evidence_needed: list[str], *, status: str = "open", risk_gate: str = "none") -> dict[str, Any]:
    return {
        "id": task_id,
        "role": role,
        "role_label": ROLE_LABELS[role],
        "title": title,
        "status": status,
        "risk_gate": risk_gate,
        "evidence_needed": evidence_needed,
        "output": "internal_draft",
    }


def build_action_board(case: dict[str, Any], evidence_dossier: dict[str, Any] | None = None) -> dict[str, Any]:
    project = case.get("project", {})
    project_name = str(project.get("title") or case.get("project") or "Untitled project")
    country = str(project.get("country") or "Unknown")
    board_id = _stable_id(project_name, country, str(case.get("created_at", "")))
    gate = _risk_gate(case, evidence_dossier)
    evidence_status = evidence_dossier.get("verification_status", "missing") if evidence_dossier else "missing"
    evidence_confidence = evidence_dossier.get("confidence", 0) if evidence_dossier else 0

    status_for_external = "blocked" if gate["blocked"] else "open"
    tasks = [
        _task(
            f"{board_id}-trade",
            "trade_lead",
            "Verify customs, HS/tariff, payment terms, Incoterms, and logistics route.",
            ["customs authority URL", "tariff/HS evidence", "payment term proof", "logistics route proof"],
            status="open",
            risk_gate="human_review_required" if gate["blocked"] else "standard_review",
        ),
        _task(
            f"{board_id}-research",
            "research_analyst",
            "Collect government, procurement, academic, and library evidence; grade each source.",
            ["government page", "procurement page", "paper/library source", "source date"],
            status="open",
            risk_gate="evidence_required",
        ),
        _task(
            f"{board_id}-investment",
            "investment_promotion_lead",
            "Map owner, developer, investor candidates, incentive policy, and project packaging gaps.",
            ["official project owner proof", "developer/investor proof", "investment agency source"],
            status=status_for_external,
            risk_gate="blocked_before_external_use" if gate["blocked"] else "approval_before_publish",
        ),
        _task(
            f"{board_id}-video",
            "video_media_producer",
            "Draft country-style video concept based on verified facts and comparable platform examples.",
            ["platform search links", "country style notes", "verified project facts"],
            status=status_for_external,
            risk_gate="human_approval_before_publish",
        ),
        _task(
            f"{board_id}-pm",
            "project_manager",
            "Prepare meeting agenda, owner decision queue, deadlines, and next internal follow-up.",
            ["meeting record", "task owner", "deadline", "decision log"],
            status="open",
            risk_gate="owner_queue" if gate["blocked"] else "none",
        ),
        _task(
            f"{board_id}-risk",
            "risk_approval_officer",
            "Keep formal outreach, quotation, payment, contract, and public publishing blocked until approval.",
            ["approval ticket", "risk trigger", "human decision", "audit log line"],
            status="pending_owner" if gate["blocked"] else "monitoring",
            risk_gate="active",
        ),
    ]

    board = {
        "ok": True,
        "id": board_id,
        "created_at": _now_iso(),
        "project": project_name,
        "country": country,
        "stage": project.get("stage", "unknown"),
        "risk_gate": gate,
        "evidence": {
            "status": evidence_status,
            "confidence": evidence_confidence,
            "dossier_id": evidence_dossier.get("id") if evidence_dossier else None,
        },
        "summary": {
            "task_count": len(tasks),
            "blocked_count": len([task for task in tasks if task["status"] in {"blocked", "pending_owner"}]),
            "open_count": len([task for task in tasks if task["status"] == "open"]),
        },
        "tasks": tasks,
        "rules": [
            "This board is internal execution control, not approval to contact customers.",
            "External messages, quotations, contracts, payments, delivery promises, and public posts require human approval.",
            "Official evidence is required before investment promotion or project confirmation.",
        ],
    }
    return board


def render_action_board(board: dict[str, Any]) -> str:
    gate = board.get("risk_gate", {})
    lines = [
        f"# Project Action Board: {board.get('project')}",
        "",
        "DRAFT - internal execution board, not approved for external sending",
        "",
        f"- Country: {board.get('country')}",
        f"- Stage: {board.get('stage')}",
        f"- Risk status: {gate.get('status')}",
        f"- Blocked: {gate.get('blocked')}",
        f"- Evidence: {board.get('evidence', {}).get('status')} ({board.get('evidence', {}).get('confidence')})",
        "",
        "## Tasks",
        "",
    ]
    for task in board.get("tasks", []):
        lines.append(f"### {task['role_label']}")
        lines.append(f"- Status: {task['status']}")
        lines.append(f"- Risk gate: {task['risk_gate']}")
        lines.append(f"- Task: {task['title']}")
        lines.append(f"- Evidence needed: {'; '.join(task['evidence_needed'])}")
        lines.append("")
    lines.extend(["## Rules", ""])
    lines.extend(f"- {rule}" for rule in board.get("rules", []))
    lines.append("")
    return "\n".join(lines)


def write_action_board(board: dict[str, Any]) -> dict[str, Any]:
    memory_dir = _memory_dir()
    report_dir = _report_dir()
    memory_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = memory_dir / f"{board['id']}.json"
    report_path = report_dir / f"{board['id']}.md"
    latest_json = memory_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    json_text = json.dumps(board, ensure_ascii=False, indent=2)
    report_text = render_action_board(board)
    json_path.write_text(json_text, encoding="utf-8")
    report_path.write_text(report_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(report_text, encoding="utf-8")
    append_audit(
        "PROJECT_ACTION_BOARD_WRITTEN",
        "DONE",
        f"Action board id={board['id']} project={board['project']} status={board['risk_gate']['status']}",
        confidence=92,
        risk="MEDIUM" if board["risk_gate"]["blocked"] else "LOW",
    )
    return {"ok": True, "board": board, "json_path": str(json_path), "report_path": str(report_path)}


def build_and_write_action_board(case: dict[str, Any], evidence_dossier: dict[str, Any] | None = None) -> dict[str, Any]:
    return write_action_board(build_action_board(case, evidence_dossier))
