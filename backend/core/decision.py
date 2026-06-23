from __future__ import annotations

from pathlib import Path

from core.models import now_iso
from core.storage import ROOT, read_json, safe_slug, write_json, write_text


VALID_DECISIONS = {"approve", "reject", "revise"}


def normalize_project_name(project: str) -> str:
    name = project.strip()
    prefix = "[Major Matter] "
    suffix = " requires owner decision"
    if name.startswith(prefix):
        name = name[len(prefix) :]
    if name.endswith(suffix):
        name = name[: -len(suffix)]
    return name.strip()


def parse_owner_reply(text: str) -> dict:
    normalized = text.strip()
    command_text = normalized[1:].strip() if normalized.startswith("/") else normalized
    lowered = command_text.lower()

    if lowered.startswith("approve"):
        decision = "approve"
        notes = command_text[len("approve") :].strip(" :-")
    elif lowered.startswith("reject"):
        decision = "reject"
        notes = command_text[len("reject") :].strip(" :-")
    elif lowered.startswith("revise"):
        decision = "revise"
        notes = command_text[len("revise") :].strip(" :-")
    else:
        decision = "unknown"
        notes = normalized

    return {
        "decision": decision,
        "valid": decision in VALID_DECISIONS,
        "notes": notes,
        "raw": text,
    }


def find_outbox_ticket(project: str) -> tuple[Path | None, dict | None]:
    slug = safe_slug(project)
    candidates = [ROOT / "comm" / "outbox" / f"{slug}.json"]
    candidates.extend(sorted((ROOT / "comm" / "outbox").glob("*.json")))
    for path in candidates:
        if not path.exists():
            continue
        ticket = read_json(path, {})
        if ticket.get("project") == project or path.stem == slug:
            return path, ticket
    return None, None


def resolve_major_matter(project: str, reply_text: str, source: str = "manual") -> dict:
    project = normalize_project_name(project)
    parsed = parse_owner_reply(reply_text)
    if not parsed["valid"]:
        return {
            "resolved": False,
            "reason": "Reply must start with approve, reject, or revise.",
            "parsed": parsed,
        }

    ticket_path, ticket = find_outbox_ticket(project)
    if not ticket:
        return {
            "resolved": False,
            "reason": f"No outbox ticket found for project: {project}",
            "parsed": parsed,
        }

    resolved_at = now_iso()
    ticket["status"] = "resolved"
    ticket["owner_decision"] = parsed["decision"]
    ticket["owner_notes"] = parsed["notes"]
    ticket["resolved_at"] = resolved_at
    ticket["source"] = source
    write_json(ticket_path, ticket)

    decision_record = {
        "created_at": resolved_at,
        "source": source,
        "project": project,
        "decision": parsed["decision"],
        "notes": parsed["notes"],
        "ticket_path": str(ticket_path),
    }
    decision_path = ROOT / "memory" / "decisions" / f"{safe_slug(project)}-{resolved_at.replace(':', '')}.json"
    write_json(decision_path, decision_record)

    continuation = build_continuation(project, parsed["decision"], parsed["notes"])
    continuation_path = ROOT / "memory" / "continuations" / f"{safe_slug(project)}-{resolved_at.replace(':', '')}.md"
    write_text(continuation_path, continuation)

    return {
        "resolved": True,
        "project": project,
        "decision": parsed["decision"],
        "ticket_path": str(ticket_path),
        "decision_path": str(decision_path),
        "continuation_path": str(continuation_path),
    }


def build_continuation(project: str, decision: str, notes: str) -> str:
    if decision == "approve":
        next_step = "Codex may continue with the approved reversible execution path and keep recording evidence."
    elif decision == "reject":
        next_step = "Codex stops the proposed action, records the rejection reason, and drafts safer alternatives."
    else:
        next_step = "Codex revises the plan according to owner conditions before continuing."

    return f"""# Continuation After Owner Decision: {project}

Created: {now_iso()}

## Owner Decision

- Decision: {decision}
- Notes: {notes or "none"}

## Codex Next Step

{next_step}
"""
