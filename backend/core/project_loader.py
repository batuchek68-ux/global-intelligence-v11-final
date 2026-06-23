from __future__ import annotations

import re
from pathlib import Path

from core.models import Project
from core.storage import ROOT


FIELD_ALIASES = {
    "title": ["title", "项目", "项目名称"],
    "country": ["country", "国家", "地区"],
    "counterparty": ["counterparty", "业主", "客户", "对手方"],
    "amount": ["amount", "金额", "合同金额"],
    "stage": ["stage", "阶段"],
    "latest_communication": ["latest_communication", "最新沟通", "当前沟通"],
    "risks": ["risks", "风险", "主要风险"],
    "next_decision": ["next_decision", "下一步决策", "需要决策"],
}


def _parse_amount(value: str) -> float:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
    if not match:
        return 0.0
    return float(match.group(0))


def _extract_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip().lstrip("-").strip()
        if not stripped or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = key.strip().strip("#").strip()
        value = value.strip()
        for normalized, aliases in FIELD_ALIASES.items():
            if key.lower() in [item.lower() for item in aliases]:
                fields[normalized] = value
    return fields


def load_project(path: Path) -> Project:
    text = path.read_text(encoding="utf-8")
    fields = _extract_fields(text)
    title = fields.get("title") or path.stem
    risk_text = fields.get("risks", "")
    risks = [item.strip() for item in re.split(r"[;；,，]", risk_text) if item.strip()]
    return Project(
        path=str(path),
        title=title,
        country=fields.get("country", "Unknown"),
        counterparty=fields.get("counterparty", "Unknown"),
        amount=_parse_amount(fields.get("amount", "0")),
        stage=fields.get("stage", "unknown"),
        latest_communication=fields.get("latest_communication", ""),
        risks=risks,
        next_decision=fields.get("next_decision", ""),
    )


def load_active_projects() -> list[Project]:
    active = ROOT / "projects" / "active"
    projects = [load_project(path) for path in sorted(active.glob("*.md"))]
    if projects:
        return projects
    sample = ROOT / "projects" / "templates" / "project_intake.md"
    if sample.exists():
        return [load_project(sample)]
    return []
