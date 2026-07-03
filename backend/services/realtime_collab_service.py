"""v12 Realtime Collaboration Service.

Multi-party realtime collaboration: messaging, file sharing,
approval workflows, and version tracking.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STORAGE = Path("backend/memory/collaboration")
STORAGE.mkdir(parents=True, exist_ok=True)


class MessageType(Enum):
    TEXT = "text"
    FILE = "file"
    APPROVAL = "approval"
    SYSTEM = "system"


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISED = "revised"


def create_conversation(
    project_id: str,
    participants: list[str],
    title: str = "",
) -> dict[str, Any]:
    """Create a new collaboration conversation."""
    conv_id = f"conv_{uuid.uuid4().hex[:12]}"
    conversation = {
        "id": conv_id,
        "project_id": project_id,
        "title": title or f"Project {project_id}",
        "participants": participants,
        "messages": [],
        "files": [],
        "approvals": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_conversation(conv_id, conversation)
    return conversation


def send_message(
    conversation_id: str,
    sender: str,
    content: str,
    message_type: MessageType = MessageType.TEXT,
    attachments: list[str] | None = None,
) -> dict[str, Any]:
    """Send a message in a conversation."""
    conv = _load_conversation(conversation_id)
    if not conv:
        return {"error": "Conversation not found"}

    msg = {
        "id": f"msg_{uuid.uuid4().hex[:12]}",
        "sender": sender,
        "content": content,
        "type": message_type.value,
        "attachments": attachments or [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    conv["messages"].append(msg)
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_conversation(conversation_id, conv)
    return msg


def create_approval(
    conversation_id: str,
    requester: str,
    title: str,
    description: str,
    approvers: list[str],
    risk_level: str = "medium",
) -> dict[str, Any]:
    """Create an approval request."""
    conv = _load_conversation(conversation_id)
    if not conv:
        return {"error": "Conversation not found"}

    approval = {
        "id": f"app_{uuid.uuid4().hex[:12]}",
        "requester": requester,
        "title": title,
        "description": description,
        "approvers": approvers,
        "risk_level": risk_level,
        "status": ApprovalStatus.PENDING.value,
        "responses": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resolved_at": None,
    }
    conv["approvals"].append(approval)
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_conversation(conversation_id, conv)

    # Also post as system message
    send_message(
        conversation_id,
        "system",
        f"Approval requested: {title} (risk: {risk_level})",
        MessageType.SYSTEM,
    )
    return approval


def resolve_approval(
    conversation_id: str,
    approval_id: str,
    approver: str,
    decision: str,  # "approve", "reject", "revise"
    comment: str = "",
) -> dict[str, Any]:
    """Resolve an approval request."""
    conv = _load_conversation(conversation_id)
    if not conv:
        return {"error": "Conversation not found"}

    for approval in conv["approvals"]:
        if approval["id"] == approval_id:
            if approver not in approval["approvers"]:
                return {"error": f"{approver} is not an authorized approver"}

            approval["status"] = decision
            approval["responses"][approver] = {
                "decision": decision,
                "comment": comment,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            approval["resolved_at"] = datetime.now(timezone.utc).isoformat()
            conv["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save_conversation(conversation_id, conv)

            send_message(
                conversation_id,
                "system",
                f"Approval '{approval['title']}' → {decision.upper()} by {approver}",
                MessageType.SYSTEM,
            )
            return approval

    return {"error": "Approval not found"}


def share_file(
    conversation_id: str,
    sender: str,
    filename: str,
    file_url: str,
    size_bytes: int = 0,
) -> dict[str, Any]:
    """Share a file in a conversation."""
    conv = _load_conversation(conversation_id)
    if not conv:
        return {"error": "Conversation not found"}

    file_entry = {
        "id": f"file_{uuid.uuid4().hex[:12]}",
        "filename": filename,
        "url": file_url,
        "size_bytes": size_bytes,
        "uploaded_by": sender,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "version": 1,
    }
    conv["files"].append(file_entry)
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_conversation(conversation_id, conv)

    send_message(
        conversation_id,
        sender,
        f"Shared file: {filename}" + (f" ({_format_size(size_bytes)})" if size_bytes else ""),
        MessageType.FILE,
        attachments=[file_url],
    )
    return file_entry


def get_conversation_summary(conversation_id: str) -> dict[str, Any]:
    """Get a summary of a conversation."""
    conv = _load_conversation(conversation_id)
    if not conv:
        return {"error": "Conversation not found"}

    pending_approvals = [a for a in conv["approvals"] if a["status"] == ApprovalStatus.PENDING.value]
    return {
        "id": conv["id"],
        "project_id": conv["project_id"],
        "title": conv["title"],
        "participants": conv["participants"],
        "message_count": len(conv["messages"]),
        "file_count": len(conv["files"]),
        "pending_approvals": len(pending_approvals),
        "last_activity": conv["updated_at"],
        "recent_messages": conv["messages"][-5:] if conv["messages"] else [],
    }


# ── Persistence ────────────────────────────────────────────────────

def _save_conversation(conv_id: str, data: dict[str, Any]) -> None:
    (STORAGE / f"{conv_id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_conversation(conv_id: str) -> dict[str, Any] | None:
    path = STORAGE / f"{conv_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _format_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
