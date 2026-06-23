from __future__ import annotations

from core.models import Project, RiskJudgment, now_iso


MAJOR_MATTER_LEVELS = {"medium", "high"}


def classify_matter(project: Project, judgment: RiskJudgment) -> dict:
    is_major = judgment.level in MAJOR_MATTER_LEVELS or judgment.needs_approval
    if is_major:
        mode = "human_decision_required"
        owner_action = "Human owner decides; Codex waits or drafts alternatives only."
    else:
        mode = "autonomous_execution"
        owner_action = "No owner decision needed; Codex executes reversible next step and records outcome."

    return {
        "created_at": now_iso(),
        "project": project.title,
        "mode": mode,
        "is_major_matter": is_major,
        "owner_action": owner_action,
        "codex_role": "24h autonomous executive",
        "github_role": "cloud AI headquarters",
        "decision_boundary": {
            "codex_can_do": [
                "collect evidence",
                "draft briefs",
                "draft video scripts",
                "prepare replies",
                "record memory",
                "run scheduled checks",
            ],
            "owner_must_decide": [
                "contract commitment",
                "payment or guarantee",
                "external publishing",
                "customer promise",
                "compliance exception",
                "high-risk project direction",
            ],
        },
    }


def build_operator_log(project: Project, judgment: RiskJudgment, actions: list[str]) -> str:
    classification = classify_matter(project, judgment)
    action_lines = "\n".join(f"- {action}" for action in actions)
    return f"""# Operator Log: {project.title}

Created: {classification["created_at"]}

## Command Model

- GitHub: cloud AI headquarters
- Codex: 24h autonomous executive
- Human owner: decides only major matters

## Matter Classification

- Mode: {classification["mode"]}
- Major matter: {classification["is_major_matter"]}
- Owner action: {classification["owner_action"]}

## Risk

- Level: {judgment.level}
- Score: {judgment.score}/100
- Triggers: {", ".join(judgment.triggers) if judgment.triggers else "none"}

## Codex Actions

{action_lines}
"""
