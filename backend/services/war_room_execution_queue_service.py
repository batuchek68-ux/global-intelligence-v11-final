from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.audit_service import append_audit


BACKEND_ROOT = Path(__file__).resolve().parents[1]
QUEUE_MEMORY_DIR = BACKEND_ROOT / "memory" / "war_room_execution"
QUEUE_REPORT_DIR = BACKEND_ROOT / "reports" / "war_room_execution"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory_dir() -> Path:
    override = os.getenv("V11_WAR_ROOM_EXECUTION_MEMORY_DIR")
    return Path(override) if override else QUEUE_MEMORY_DIR


def _report_dir() -> Path:
    override = os.getenv("V11_WAR_ROOM_EXECUTION_REPORT_DIR")
    return Path(override) if override else QUEUE_REPORT_DIR


def _stable_id(*parts: str) -> str:
    raw = "|".join(str(part).strip().lower() for part in parts if str(part).strip())
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _as_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _task(
    queue_id: str,
    index: int,
    *,
    role: str,
    task: str,
    source: str,
    evidence_needed: list[str],
    risk_gate: str,
    status: str = "open",
    blocked_actions: list[str] | None = None,
    output: str = "internal_draft",
) -> dict[str, Any]:
    return {
        "id": f"{queue_id}-{index:02d}",
        "role": role,
        "task": task,
        "source": source,
        "evidence_needed": [item for item in evidence_needed if item],
        "status": status,
        "risk_gate": risk_gate,
        "blocked_actions": blocked_actions or [],
        "human_approval_required": risk_gate in {"approval_required", "blocked_before_external_use", "owner_review"},
        "output": output,
    }


def build_war_room_execution_queue(war_room: dict[str, Any]) -> dict[str, Any]:
    """Turn a war room package into a persistent execution queue.

    The queue is intentionally conservative: anything tied to outreach, investment
    promotion, video publishing, quotation, payment, contract, customs commitment,
    or public claims stays draft-only until human approval.
    """
    room = war_room.get("war_room", war_room)
    objective = _as_text(room.get("objective"), "v11 industry war room")
    country = _as_text(room.get("country"), "Unknown")
    queue_id = _stable_id(room.get("id"), objective, country, room.get("created_at"))
    blocked_actions = room.get("approval_boundary", {}).get("blocked_actions", [])
    if not isinstance(blocked_actions, list):
        blocked_actions = []

    tasks: list[dict[str, Any]] = []
    index = 1

    for item in room.get("search_confirmation", {}).get("priority_queries", [])[:8]:
        query = _as_text(item.get("query") if isinstance(item, dict) else item)
        intent = _as_text(item.get("intent") if isinstance(item, dict) else "", "search_verification")
        required = bool(item.get("required")) if isinstance(item, dict) else True
        tasks.append(
            _task(
                queue_id,
                index,
                role="research_analyst",
                task=f"Run and record source evidence for query: {query}",
                source=f"search_confirmation.{intent}",
                evidence_needed=["official URL", "source date", "source type", "relevant excerpt", "confidence note"],
                risk_gate="evidence_required" if required else "standard_review",
                status="open",
                output="evidence_record",
            )
        )
        index += 1

    evidence = room.get("evidence", {})
    if evidence.get("verification_status") != "officially_supported":
        tasks.append(
            _task(
                queue_id,
                index,
                role="risk_approval_officer",
                task="Upgrade evidence from lead-only or partial support to official confirmation before project confirmation.",
                source="evidence.verification_status",
                evidence_needed=["government/customs/procurement URL", "official company URL if relevant", "collection date", "contradiction check"],
                risk_gate="approval_required",
                status="blocked",
                blocked_actions=blocked_actions,
                output="evidence_gap_report",
            )
        )
        index += 1

    for action in room.get("project_execution", {}).get("next_actions", [])[:8]:
        tasks.append(
            _task(
                queue_id,
                index,
                role="project_manager",
                task=_as_text(action),
                source="project_execution.next_actions",
                evidence_needed=["task owner", "deadline", "source link", "decision log"],
                risk_gate="owner_review" if room.get("approval_boundary", {}).get("human_approval_required") else "standard_review",
                status="open",
                blocked_actions=blocked_actions,
                output="project_followup_item",
            )
        )
        index += 1

    for role in room.get("team", {}).get("roles", [])[:8]:
        role_name = _as_text(role.get("role") if isinstance(role, dict) else "team_member", "team_member")
        next_step = _as_text(role.get("next_step") if isinstance(role, dict) else role)
        tasks.append(
            _task(
                queue_id,
                index,
                role=role_name,
                task=next_step,
                source="team.roles.next_step",
                evidence_needed=["role output", "review note", "risk boundary"],
                risk_gate="standard_review",
                status="open",
                output="role_work_product",
            )
        )
        index += 1

    for task in room.get("action_board", {}).get("tasks", [])[:8]:
        title = _as_text(task.get("title") or task.get("task") if isinstance(task, dict) else task)
        role = _as_text(task.get("role") or task.get("owner") if isinstance(task, dict) else "project_manager", "project_manager")
        task_status = _as_text(task.get("status") if isinstance(task, dict) else "open", "open")
        tasks.append(
            _task(
                queue_id,
                index,
                role=role,
                task=title,
                source="action_board.tasks",
                evidence_needed=task.get("evidence_needed", []) if isinstance(task, dict) else ["evidence note"],
                risk_gate=_as_text(task.get("risk_gate") if isinstance(task, dict) else "standard_review", "standard_review"),
                status=task_status,
                blocked_actions=blocked_actions if task_status in {"blocked", "pending_owner"} else [],
                output=_as_text(task.get("output") if isinstance(task, dict) else "internal_draft", "internal_draft"),
            )
        )
        index += 1

    for item in room.get("video_center", {}).get("platform_searches", [])[:6]:
        platform = _as_text(item.get("platform") if isinstance(item, dict) else "video_platform")
        keyword = _as_text(item.get("keyword") if isinstance(item, dict) else item)
        tasks.append(
            _task(
                queue_id,
                index,
                role="video_media_producer",
                task=f"Study platform examples and draft original video angle for {platform}: {keyword}",
                source="video_center.platform_searches",
                evidence_needed=["reference links", "style notes", "original script outline", "approval boundary"],
                risk_gate="blocked_before_external_use",
                status="blocked",
                blocked_actions=["public publishing", "unapproved outreach", *blocked_actions],
                output="draft_video_brief",
            )
        )
        index += 1

    open_count = len([item for item in tasks if item["status"] == "open"])
    blocked_count = len([item for item in tasks if item["status"] in {"blocked", "pending_owner"}])
    queue = {
        "ok": True,
        "id": queue_id,
        "created_at": _now_iso(),
        "mode": "war_room_execution_queue",
        "war_room_id": room.get("id"),
        "objective": objective,
        "country": country,
        "summary": {
            "task_count": len(tasks),
            "open_count": open_count,
            "blocked_count": blocked_count,
            "evidence_required_count": len([item for item in tasks if item["risk_gate"] == "evidence_required"]),
            "approval_required_count": len([item for item in tasks if item["human_approval_required"]]),
        },
        "tasks": tasks,
        "rules": [
            "Queue items are internal execution controls, not permission to contact external parties.",
            "Official evidence is required before project confirmation, investment promotion, customs conclusions, or feasibility claims.",
            "External replies, quotation, payment, contract, customer commitment, and public publishing require human approval.",
        ],
    }
    return queue


def render_war_room_execution_queue(queue: dict[str, Any]) -> str:
    summary = queue.get("summary", {})
    lines = [
        f"# v11 War Room Execution Queue: {queue.get('objective')}",
        "",
        "DRAFT - internal execution queue, not approved for external sending",
        "",
        f"- Country: {queue.get('country')}",
        f"- Tasks: {summary.get('task_count', 0)}",
        f"- Open: {summary.get('open_count', 0)}",
        f"- Blocked: {summary.get('blocked_count', 0)}",
        f"- Evidence required: {summary.get('evidence_required_count', 0)}",
        f"- Approval required: {summary.get('approval_required_count', 0)}",
        "",
        "## Queue",
        "",
    ]
    for item in queue.get("tasks", []):
        lines.append(f"### {item.get('id')} | {item.get('role')}")
        lines.append(f"- Status: {item.get('status')}")
        lines.append(f"- Risk gate: {item.get('risk_gate')}")
        lines.append(f"- Source: {item.get('source')}")
        lines.append(f"- Task: {item.get('task')}")
        lines.append(f"- Evidence needed: {'; '.join(item.get('evidence_needed', []))}")
        if item.get("blocked_actions"):
            lines.append(f"- Blocked actions: {'; '.join(sorted(set(item.get('blocked_actions', []))))}")
        lines.append("")
    lines.extend(["## Rules", ""])
    lines.extend(f"- {rule}" for rule in queue.get("rules", []))
    lines.append("")
    return "\n".join(lines)


def write_war_room_execution_queue(queue: dict[str, Any]) -> dict[str, Any]:
    memory_dir = _memory_dir()
    report_dir = _report_dir()
    memory_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = memory_dir / f"{queue['id']}.json"
    report_path = report_dir / f"{queue['id']}.md"
    latest_json = memory_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    json_text = json.dumps(queue, ensure_ascii=False, indent=2)
    report_text = render_war_room_execution_queue(queue)
    json_path.write_text(json_text, encoding="utf-8")
    report_path.write_text(report_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(report_text, encoding="utf-8")
    append_audit(
        "WAR_ROOM_EXECUTION_QUEUE_WRITTEN",
        "DONE",
        f"War room execution queue id={queue['id']} tasks={queue['summary']['task_count']} blocked={queue['summary']['blocked_count']}",
        confidence=94,
        risk="MEDIUM" if queue["summary"]["blocked_count"] else "LOW",
    )
    return {"ok": True, "queue": queue, "json_path": str(json_path), "report_path": str(report_path)}


def build_and_write_war_room_execution_queue(war_room: dict[str, Any]) -> dict[str, Any]:
    return write_war_room_execution_queue(build_war_room_execution_queue(war_room))


def read_latest_war_room_execution_queue() -> dict[str, Any]:
    memory_path = _memory_dir() / "latest.json"
    report_path = _report_dir() / "latest.md"
    queue: dict[str, Any] = {}
    report = ""
    if memory_path.is_file():
        try:
            queue = json.loads(memory_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            queue = {}
    if report_path.is_file():
        report = report_path.read_text(encoding="utf-8", errors="replace")
    return {
        "ok": bool(queue),
        "queue": queue,
        "report": report,
        "json_path": str(memory_path),
        "report_path": str(report_path),
        "missing": [] if queue else ["memory/war_room_execution/latest.json"],
        "note": "Read-only queue view. It does not send external messages or bypass approval gates.",
    }
