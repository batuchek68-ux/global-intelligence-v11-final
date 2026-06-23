from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage


def approval_message(ticket: dict) -> str:
    triggers = ", ".join(ticket.get("triggers", [])) or "none"
    return "\n".join(
        [
            "International Trade Cloud OS approval needed",
            f"Project: {ticket.get('project', 'Unknown')}",
            f"Country: {ticket.get('country', 'Unknown')}",
            f"Counterparty: {ticket.get('counterparty', 'Unknown')}",
            f"Risk: {ticket.get('risk_level', 'unknown')} ({ticket.get('risk_score', 0)}/100)",
            f"Triggers: {triggers}",
            f"Question: {ticket.get('question', 'Review required')}",
            "",
            "Reply: /approve, /reject, or /revise with conditions.",
        ]
    )


def post_json_webhook(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return {"sent": True, "status": response.status}
    except Exception as exc:  # pragma: no cover - network depends on runtime secrets.
        return {"sent": False, "reason": str(exc)}


def notify_enterprise_wechat(ticket: dict) -> dict:
    webhook = os.getenv("WECHAT_WEBHOOK_URL") or os.getenv("ENTERPRISE_WECHAT_WEBHOOK_URL")
    if not webhook:
        return {"sent": False, "reason": "WECHAT_WEBHOOK_URL not configured"}
    return post_json_webhook(
        webhook,
        {"msgtype": "text", "text": {"content": approval_message(ticket)}},
    )


def notify_feishu(ticket: dict) -> dict:
    webhook = os.getenv("FEISHU_WEBHOOK_URL") or os.getenv("LARK_WEBHOOK_URL")
    if not webhook:
        return {"sent": False, "reason": "FEISHU_WEBHOOK_URL not configured"}
    return post_json_webhook(
        webhook,
        {"msg_type": "text", "content": {"text": approval_message(ticket)}},
    )


def notify_email(ticket: dict) -> dict:
    host = os.getenv("SMTP_HOST")
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM") or username
    recipients = [item.strip() for item in os.getenv("ALERT_EMAIL_TO", "").split(",") if item.strip()]
    if not all([host, username, password, sender]) or not recipients:
        return {"sent": False, "reason": "SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD/ALERT_EMAIL_TO not configured"}

    message = EmailMessage()
    message["Subject"] = f"Approval needed: {ticket.get('project', 'project')}"
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(approval_message(ticket))

    port = int(os.getenv("SMTP_PORT", "465"))
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
        return {"sent": True, "recipients": recipients}
    except Exception as exc:  # pragma: no cover - network depends on runtime secrets.
        return {"sent": False, "reason": str(exc)}


def notify_major_matter(ticket: dict) -> dict:
    return {
        "enterprise_wechat": notify_enterprise_wechat(ticket),
        "feishu": notify_feishu(ticket),
        "email": notify_email(ticket),
    }
