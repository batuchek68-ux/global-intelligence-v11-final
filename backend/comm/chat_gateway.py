from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any

from backend.services.audit_service import append_audit


BACKEND_ROOT = Path(__file__).resolve().parents[1]
OUTBOX = BACKEND_ROOT / "comm" / "outbox"


def build_chat_reply_draft(channel: str, recipient: str, message: str, context: dict[str, Any] | None = None) -> dict:
    return {
        "channel": channel,
        "recipient": recipient,
        "message": message,
        "context": context or {},
        "status": "draft_not_approved_for_sending",
        "approval_required": True,
        "safety_rule": "Draft -> Self Review -> Policy Check -> Human Approval -> Send",
    }


def save_chat_reply_draft(draft: dict) -> Path:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in f"{draft.get('channel')}-{draft.get('recipient')}")
    slug = "-".join(part for part in slug.split("-") if part)[:80] or "chat-reply"
    path = OUTBOX / f"{slug}.chat-draft.json"
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    append_audit(
        "CHAT_REPLY_DRAFT_CREATED",
        "DONE",
        f"Created gated chat draft for {draft.get('channel')} recipient={draft.get('recipient')}; not sent.",
        risk="MEDIUM",
    )
    return path


def approved_to_send(draft: dict) -> bool:
    if draft.get("approved_by_human") is True:
        return True
    if os.getenv("ALLOW_APPROVED_CHAT_SEND") == "1" and draft.get("status") == "approved":
        return True
    return False


def send_approved_webhook_message(draft: dict) -> dict:
    """Send only after explicit approval; otherwise keep the message in outbox."""
    if not approved_to_send(draft):
        path = save_chat_reply_draft(draft)
        return {"sent": False, "reason": "human approval required", "draft_path": str(path)}

    webhook = os.getenv("WECHAT_WEBHOOK_URL") or os.getenv("ENTERPRISE_WECHAT_WEBHOOK_URL")
    if not webhook:
        return {"sent": False, "reason": "WECHAT_WEBHOOK_URL not configured"}

    payload = {"msgtype": "text", "text": {"content": str(draft.get("message", ""))}}
    request = urllib.request.Request(
        webhook,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        append_audit(
            "APPROVED_CHAT_REPLY_SENT",
            "DONE",
            f"Sent approved chat reply through {draft.get('channel')}; status={response.status}.",
            risk="MEDIUM",
        )
        return {"sent": True, "status": response.status}
