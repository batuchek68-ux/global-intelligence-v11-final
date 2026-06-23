from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

from core.models import Project, RiskJudgment, now_iso
from core.storage import write_json


def build_approval_ticket(project: Project, judgment: RiskJudgment) -> dict:
    return {
        "created_at": now_iso(),
        "channel": "wechat_or_enterprise_wechat",
        "status": "waiting",
        "project": project.title,
        "country": project.country,
        "counterparty": project.counterparty,
        "risk_level": judgment.level,
        "risk_score": judgment.score,
        "triggers": judgment.triggers,
        "question": f"Approve next step for {project.title}? {judgment.recommendation}",
        "reply_expected": "approve / reject / revise with conditions",
    }


def merge_existing_ticket(ticket: dict, existing: dict | None) -> dict:
    if not existing:
        return ticket
    preserved = dict(ticket)
    for key in [
        "created_at",
        "status",
        "owner_decision",
        "owner_notes",
        "resolved_at",
        "source",
        "github_issue",
        "webhook",
    ]:
        if key in existing:
            preserved[key] = existing[key]
    return preserved


def write_outbox(ticket: dict, path: Path) -> Path:
    return write_json(path, ticket)


def maybe_send_webhook(ticket: dict) -> dict:
    webhook = os.getenv("WECHAT_WEBHOOK_URL")
    if not webhook:
        return {"sent": False, "reason": "WECHAT_WEBHOOK_URL not configured"}

    payload = {
        "msgtype": "text",
        "text": {
            "content": (
                f"International Trade AI approval needed\n"
                f"Project: {ticket['project']}\n"
                f"Risk: {ticket['risk_level']} ({ticket['risk_score']}/100)\n"
                f"Question: {ticket['question']}"
            )
        },
    }
    request = urllib.request.Request(
        webhook,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return {"sent": True, "status": response.status}
    except Exception as exc:  # pragma: no cover - network depends on runtime secrets.
        return {"sent": False, "reason": str(exc)}
