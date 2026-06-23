from __future__ import annotations

from core.models import Project, RiskJudgment


HIGH_RISK_KEYWORDS = [
    "sanction",
    "export control",
    "customs",
    "compliance",
    "arbitration",
    "claim",
    "breach",
    "guarantee",
    "payment",
    "political",
    "制裁",
    "出口管制",
    "海关",
    "合规",
    "仲裁",
    "索赔",
    "违约",
    "保函",
    "付款",
    "政治",
]


def judge_project(project: Project, approval_amount: float = 100000.0) -> RiskJudgment:
    text = " ".join(
        [
            project.title,
            project.country,
            project.counterparty,
            project.stage,
            project.latest_communication,
            " ".join(project.risks),
            project.next_decision,
        ]
    ).lower()
    triggers: list[str] = []
    score = 20

    for keyword in HIGH_RISK_KEYWORDS:
        if keyword.lower() in text:
            triggers.append(keyword)
            score += 18

    if project.amount >= approval_amount:
        triggers.append(f"amount>={approval_amount:.0f}")
        score += 22

    if not project.latest_communication:
        triggers.append("missing_latest_communication")
        score += 8

    score = min(score, 100)
    if score >= 75:
        level = "high"
    elif score >= 45:
        level = "medium"
    else:
        level = "low"

    needs_approval = level != "low" or bool(triggers)
    if needs_approval:
        recommendation = "Create an approval ticket before external commitment, payment, contract change, or public communication."
    else:
        recommendation = "Proceed with a small reversible next step and keep the learning record updated."

    return RiskJudgment(
        level=level,
        score=score,
        triggers=triggers,
        recommendation=recommendation,
        needs_approval=needs_approval,
    )
