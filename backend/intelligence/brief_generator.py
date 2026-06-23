from __future__ import annotations

import os
from urllib.parse import quote

from core.models import Project, RiskJudgment, now_iso


def build_research_brief(project: Project, judgment: RiskJudgment, topic: str | None = None) -> str:
    focus = topic or os.getenv("OPS_TOPIC") or "international engineering trade compliance risk"
    search_links = [
        f"https://www.bing.com/search?q={quote(focus + ' ' + project.country)}",
        f"https://scholar.google.com/scholar?q={quote(focus + ' ' + project.country)}",
    ]
    return f"""# Daily Intelligence Brief: {project.title}

Generated: {now_iso()}

## Focus

{focus}

## Project

- Country: {project.country}
- Counterparty: {project.counterparty}
- Stage: {project.stage}
- Amount: {project.amount}
- Next decision: {project.next_decision or "Not provided"}

## Risk Signal

- Level: {judgment.level}
- Score: {judgment.score}/100
- Triggers: {", ".join(judgment.triggers) if judgment.triggers else "none"}
- Recommendation: {judgment.recommendation}

## Research Leads

- Bing lead: {search_links[0]}
- Scholar lead: {search_links[1]}

## Operator Notes

1. Verify country policy, customs, tax, payment, and logistics constraints.
2. Check counterparty reliability and contract exposure before commitments.
3. Keep video/public content in draft mode until human approval.
"""
