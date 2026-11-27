"""judge_project 的溯源前置硬校验包装。

落地方式：把本文件放到 backend/core/judge_with_provenance.py，
在需要证据入库的调用点用 judge_project_with_provenance() 替代 judge_project()。
原 judge_project() 保持签名与行为不变，向后兼容。
"""
from __future__ import annotations

from typing import Any

from backend.intelligence.compliant_acquisition import validate_provenance
from core.models import Project, RiskJudgment

from .judge import judge_project


def judge_project_with_provenance(
    project: Project,
    records: list[dict[str, Any]] | None = None,
    approval_amount: float = 100000.0,
) -> tuple[RiskJudgment, dict[str, Any]]:
    """先校验 provenance，再打分；任一证据缺字段即强制人工审批。"""
    accepted, rejected = validate_provenance(records or [])
    judgment = judge_project(project, approval_amount)

    if rejected:
        judgment.needs_approval = True
        judgment.triggers = [*judgment.triggers, "provenance_rejected"]
        judgment.recommendation = (
            f"Rejected {len(rejected)} evidence record(s): invalid or missing provenance. "
            "Human approval required before any external action."
        )

    return judgment, {
        "accepted_count": len(accepted),
        "rejected": rejected,
        "accepted_records": accepted,
    }
