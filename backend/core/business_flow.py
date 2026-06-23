from __future__ import annotations

from core.models import Project, RiskJudgment, now_iso


def build_meeting_followup(project: Project) -> dict:
    return {
        "channels": ["WeChat", "QQ Meeting"],
        "status": "draft_only",
        "agenda": [
            f"Confirm current stage for {project.title}",
            "Confirm owner/customer decision maker and contact window",
            "Collect missing contract, logistics, customs, and payment evidence",
            "Assign next follow-up owner and deadline",
        ],
        "minutes_template": [
            "Participants:",
            "Key facts confirmed:",
            "Open risks:",
            "Decisions made by human owner:",
            "Next follow-up time:",
        ],
    }


def build_content_pipeline(project: Project, judgment: RiskJudgment) -> dict:
    platforms = ["Douyin", "Video Channel", "TikTok", "YouTube"]
    return {
        "status": "draft_not_approved_for_publishing",
        "platforms": platforms,
        "publishing_rule": "Draft -> self review -> policy check -> human approval -> publish",
        "draft_topics": [
            f"{project.country} engineering trade update",
            "EPC project risk and opportunity",
            "Customs, logistics, payment, and compliance watch",
        ],
        "blocked_without_human_approval": judgment.needs_approval,
    }


def build_business_flow(project: Project, judgment: RiskJudgment) -> dict:
    return {
        "created_at": now_iso(),
        "project": project.title,
        "real_work_coverage": {
            "international_trade": [
                "market intelligence",
                "counterparty and owner tracking",
                "EPC/tender/procurement opportunity watch",
                "customs/logistics/payment/compliance risk list",
            ],
            "domestic_project_coordination": [
                "internal task assignment",
                "supplier and partner follow-up",
                "evidence collection",
                "owner decision queue",
            ],
            "meeting_followup": build_meeting_followup(project),
            "content_operations": build_content_pipeline(project, judgment),
        },
        "automation_boundary": {
            "autonomous": [
                "prepare draft reply",
                "prepare meeting agenda and minutes template",
                "prepare video script and platform checklist",
                "prepare risk brief and owner inbox item",
            ],
            "human_required": [
                "send customer commitment",
                "publish public video",
                "confirm price or delivery date",
                "sign contract or approve payment",
            ],
        },
    }


def render_business_flow(flow: dict) -> str:
    coverage = flow["real_work_coverage"]
    lines = [
        f"# Business Flow: {flow['project']}",
        "",
        f"Created: {flow['created_at']}",
        "",
        "## International Trade",
        "",
    ]
    lines.extend(f"- {item}" for item in coverage["international_trade"])
    lines.extend(["", "## Domestic Project Coordination", ""])
    lines.extend(f"- {item}" for item in coverage["domestic_project_coordination"])
    lines.extend(["", "## WeChat / QQ Meeting Follow-up", ""])
    for item in coverage["meeting_followup"]["agenda"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Video Content Operations", ""])
    lines.append("- Platforms: " + ", ".join(coverage["content_operations"]["platforms"]))
    lines.append(f"- Status: {coverage['content_operations']['status']}")
    lines.append(f"- Rule: {coverage['content_operations']['publishing_rule']}")
    lines.extend(["", "## Automation Boundary", ""])
    lines.append("- Autonomous: " + ", ".join(flow["automation_boundary"]["autonomous"]))
    lines.append("- Human required: " + ", ".join(flow["automation_boundary"]["human_required"]))
    lines.append("")
    return "\n".join(lines)
