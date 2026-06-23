from __future__ import annotations

from core.models import Project, RiskJudgment, now_iso


def build_execution_record(
    project: Project,
    judgment: RiskJudgment,
    actions: list[str],
    classification: dict,
    owner_decision: str | None = None,
) -> dict:
    if classification.get("is_major_matter") and not owner_decision:
        status = "waiting_for_owner"
        result = "Codex paused external action and prepared an owner decision request."
    elif owner_decision:
        status = "continued_after_owner_decision"
        result = f"Codex continued according to owner decision: {owner_decision}."
    else:
        status = "autonomous_executed"
        result = "Codex executed the reversible low-risk operating step."

    return {
        "created_at": now_iso(),
        "project": project.title,
        "mode": classification.get("mode"),
        "status": status,
        "risk_level": judgment.level,
        "risk_score": judgment.score,
        "requires_owner": classification.get("is_major_matter", False) and not owner_decision,
        "owner_decision": owner_decision,
        "actions": actions,
        "result": result,
    }
