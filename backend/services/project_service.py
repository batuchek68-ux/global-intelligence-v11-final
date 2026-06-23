from __future__ import annotations

from typing import Any

from backend.models.schemas import ProjectIntake, now_iso


HIGH_RISK_KEYWORDS = [
    "contract",
    "payment",
    "sanction",
    "export control",
    "customs",
    "government",
    "arbitration",
    "claim",
    "合同",
    "付款",
    "制裁",
    "出口管制",
    "海关",
    "政府",
    "仲裁",
    "索赔",
]


def build_project_intake(data: dict[str, Any]) -> ProjectIntake:
    return ProjectIntake(
        title=str(data.get("title") or data.get("project") or "Untitled project"),
        country=str(data.get("country") or "Unknown"),
        counterparty=str(data.get("counterparty") or "Unknown"),
        amount_usd=float(data.get("amount_usd") or data.get("amount") or 0),
        stage=str(data.get("stage") or "intake"),
        latest_communication=str(data.get("latest_communication") or ""),
        risks=list(data.get("risks") or []),
        next_decision=str(data.get("next_decision") or ""),
    )


def analyze_project(data: dict[str, Any]) -> dict[str, Any]:
    project = build_project_intake(data)
    text = " ".join(
        [
            project.title,
            project.country,
            project.counterparty,
            project.stage,
            project.latest_communication,
            project.next_decision,
            " ".join(project.risks),
        ]
    ).lower()
    triggers = [item for item in HIGH_RISK_KEYWORDS if item.lower() in text]
    if project.amount_usd >= 100000:
        triggers.append("amount >= 100000 USD")

    needs_approval = bool(triggers)
    risk_level = "high" if needs_approval else "low"
    return {
        "ok": True,
        "created_at": now_iso(),
        "project": project.__dict__,
        "risk_level": risk_level,
        "needs_human_approval": needs_approval,
        "triggers": triggers,
        "allowed_actions": [
            "prepare internal analysis",
            "prepare draft reply",
            "prepare meeting agenda",
            "prepare video/content draft",
        ],
        "blocked_actions": [
            "sign contract",
            "approve payment",
            "quote final price",
            "promise delivery",
            "publish public content without approval",
        ],
    }
