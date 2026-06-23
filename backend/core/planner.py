from __future__ import annotations

from core.models import Project, RiskJudgment


def plan_actions(project: Project, judgment: RiskJudgment) -> list[str]:
    actions = [
        f"Update project file for {project.title} with latest communication and evidence.",
        "Generate daily research brief and attach it to the decision record.",
        "Draft a short video script for internal/external communication review.",
    ]
    if judgment.needs_approval:
        actions.insert(0, "Send approval ticket to human owner before any external commitment.")
        actions.append("Wait for approval reply, then write the reply into memory before continuing.")
    else:
        actions.append("Execute a reversible pilot step and record result in memory.")
    return actions
