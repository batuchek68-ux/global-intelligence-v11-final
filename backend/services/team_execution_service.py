from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.audit_service import append_audit
from backend.services.intelligence_center_service import build_intelligence_search_system, build_video_production_center
from backend.services.knowledge_benchmark_service import score_answer
from backend.services.project_intelligence_service import build_project_search_plan, classify_project_stage
from backend.services.social_communication_service import assess_social_context


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEAM_MEMORY_DIR = BACKEND_ROOT / "memory" / "team_execution"
TEAM_REPORT_DIR = BACKEND_ROOT / "reports" / "team_execution"

TEAM_ROLES = {
    "trade_lead": {
        "label": "International trade lead",
        "responsibility": "customs, payment, Incoterms, logistics, supplier/counterparty risk",
    },
    "research_analyst": {
        "label": "Research intelligence analyst",
        "responsibility": "papers, libraries, government reports, evidence grading, technical feasibility",
    },
    "investment_promotion_lead": {
        "label": "Investment promotion lead",
        "responsibility": "project packaging, developer/owner mapping, ROI narrative, investment promotion material",
    },
    "video_media_producer": {
        "label": "Video and media producer",
        "responsibility": "platform keywords, country style, short video scripts, visual proof plan",
    },
    "project_manager": {
        "label": "Project execution manager",
        "responsibility": "task plan, meeting follow-up, decision queue, owner inbox, timeline",
    },
    "risk_approval_officer": {
        "label": "Risk and approval officer",
        "responsibility": "contracts, payments, sanctions, export control, external communication gates",
    },
}

HIGH_RISK_SIGNALS = [
    "contract",
    "payment",
    "price",
    "delivery",
    "sanction",
    "export control",
    "government",
    "customs",
    "合同",
    "付款",
    "报价",
    "交期",
    "制裁",
    "出口管制",
    "政府",
    "海关",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(*parts: str) -> str:
    raw = "|".join(str(part).strip().lower() for part in parts if part)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _report_dir() -> Path:
    override = os.getenv("V11_TEAM_EXECUTION_REPORT_DIR")
    return Path(override) if override else TEAM_REPORT_DIR


def _memory_dir() -> Path:
    override = os.getenv("V11_TEAM_EXECUTION_MEMORY_DIR")
    return Path(override) if override else TEAM_MEMORY_DIR


def _as_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or fallback
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()] or [value.strip()]
    return fallback


def assess_execution_risk(text: str, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    lower = text.lower()
    hits = [item for item in HIGH_RISK_SIGNALS if item.lower() in lower]
    official_evidence = [
        item for item in (evidence or [])
        if str(item.get("source_type", "")).lower() in {"government", "official", "procurement"}
        or "gov" in str(item.get("url", "")).lower()
    ]
    needs_approval = bool(hits)
    if any(item in hits for item in ["government", "customs", "政府", "海关"]) and not official_evidence:
        needs_approval = True
    return {
        "risk_level": "high" if hits else "medium",
        "signals": hits,
        "official_evidence_count": len(official_evidence),
        "needs_human_approval": needs_approval,
        "blocked_actions": [
            "external commitment",
            "formal quotation",
            "contract language",
            "payment approval",
            "public publishing",
        ] if needs_approval else [],
    }


def build_team_execution_package(
    objective: str,
    *,
    country: str = "Kazakhstan",
    industries: list[str] | str | None = None,
    evidence: list[dict[str, Any]] | None = None,
    audience: str = "internal",
) -> dict[str, Any]:
    industries_list = _as_list(industries, ["infrastructure", "mining", "logistics", "energy"])
    evidence = evidence or []
    package_id = _stable_id(objective, country, ",".join(industries_list))
    project_search = build_project_search_plan(objective, country)
    intelligence_system = build_intelligence_search_system([objective], [country], industries_list)
    video_center = build_video_production_center([objective], [country], industries_list[:2])
    risk = assess_execution_risk(f"{objective} {country} {' '.join(industries_list)}", evidence)
    social = assess_social_context(
        "enterprise_wechat",
        objective,
        authorization={"scope": "draft_only"},
        evidence=evidence,
        audience=audience,
    )
    stage = classify_project_stage(" ".join(str(item.get("snippet", "")) for item in evidence) or objective)

    deliverables = [
        {"owner": "trade_lead", "name": "Customs and trade risk checklist", "status": "draft", "path": None},
        {"owner": "research_analyst", "name": "Evidence-grade research brief", "status": "draft", "path": None},
        {"owner": "investment_promotion_lead", "name": "Investment promotion one-page brief", "status": "draft", "path": None},
        {"owner": "video_media_producer", "name": "Country-style short video script plan", "status": "draft", "path": None},
        {"owner": "project_manager", "name": "Meeting agenda, next actions, and decision queue", "status": "draft", "path": None},
        {"owner": "risk_approval_officer", "name": "Approval gate and blocked action list", "status": "active", "path": None},
    ]

    role_work = []
    for role_id, role in TEAM_ROLES.items():
        role_work.append(
            {
                "role": role_id,
                "label": role["label"],
                "responsibility": role["responsibility"],
                "next_actions": _role_actions(role_id, country),
                "evidence_needed": _role_evidence(role_id),
            }
        )

    answer_quality = score_answer(
        f"How should v11 execute: {objective}",
        "Use official evidence, search plan, project execution package, action checklist, risk approval gate, and professional domain deliverables.",
        evidence=evidence,
    )

    result = {
        "ok": True,
        "id": package_id,
        "created_at": _now_iso(),
        "objective": objective,
        "country": country,
        "industries": industries_list,
        "project_stage": stage,
        "team_roles": role_work,
        "search_plan": {
            "project": project_search,
            "intelligence_categories": intelligence_system["categories"],
            "video_platform_searches": video_center["platform_searches"][:24],
        },
        "deliverables": deliverables,
        "risk": risk,
        "social_communication_gate": social,
        "answer_quality_model": answer_quality,
        "operating_rule": "v11 acts as a project team: evidence first, action plan second, approval gate before any external commitment.",
    }
    _persist_team_package(result)
    return result


def _role_actions(role_id: str, country: str) -> list[str]:
    return {
        "trade_lead": [
            f"Build customs, HS code, tariff, payment, and logistics search terms for {country}.",
            "Prepare Incoterms, logistics, customs, and payment risk checklist.",
            "Identify what must be verified by broker, bank, or customs authority.",
        ],
        "research_analyst": [
            "Collect government, academic, library, and industry evidence.",
            "Grade sources by official, primary, secondary, social, and video tiers.",
            "Flag unsupported claims before reporting.",
        ],
        "investment_promotion_lead": [
            "Identify owner, developer, government authority, and investor candidates.",
            "Draft investment promotion one-page brief.",
            "Separate confirmed facts from opportunity hypotheses.",
        ],
        "video_media_producer": [
            "Track YouTube, TikTok, Douyin, and local platform examples.",
            "Extract video style patterns without copying protected content.",
            "Draft short video structure tied to verified project facts.",
        ],
        "project_manager": [
            "Turn findings into tasks, deadlines, owners, and meeting agenda.",
            "Place high-risk decisions into owner inbox.",
            "Maintain next-action board until evidence is complete.",
        ],
        "risk_approval_officer": [
            "Block formal quotes, delivery promises, contracts, payments, and public publishing.",
            "Escalate sanctions, export control, customs, and government commitment risks.",
            "Verify audit and approval records before release.",
        ],
    }[role_id]


def _role_evidence(role_id: str) -> list[str]:
    return {
        "trade_lead": ["customs authority URL", "tariff/HS evidence", "payment term evidence", "logistics route proof"],
        "research_analyst": ["government report", "paper/library source", "source date", "relevance note"],
        "investment_promotion_lead": ["government project page", "owner/developer proof", "investment agency proof"],
        "video_media_producer": ["platform search URL", "comparable video notes", "country style notes"],
        "project_manager": ["task owner", "deadline", "meeting record", "decision log"],
        "risk_approval_officer": ["approval ticket", "risk trigger", "human decision", "audit log line"],
    }[role_id]


def _persist_team_package(package: dict[str, Any]) -> None:
    memory_dir = _memory_dir()
    report_dir = _report_dir()
    memory_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = memory_dir / f"{package['id']}.json"
    report_path = report_dir / f"{package['id']}.md"
    json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_team_execution_report(package), encoding="utf-8")
    append_audit(
        "TEAM_EXECUTION_PACKAGE",
        "DONE",
        f"Built team execution package id={package['id']} objective={package['objective'][:120]}",
        confidence=93,
        risk="MEDIUM" if package["risk"]["needs_human_approval"] else "LOW",
    )


def render_team_execution_report(package: dict[str, Any]) -> str:
    lines = [
        f"# v11 Team Execution Package: {package['objective']}",
        "",
        "DRAFT - internal execution package, not approved for external sending",
        "",
        f"- Country: {package['country']}",
        f"- Industries: {', '.join(package['industries'])}",
        f"- Risk level: {package['risk']['risk_level']}",
        f"- Human approval required: {package['risk']['needs_human_approval']}",
        "",
        "## Team Roles",
        "",
    ]
    for role in package["team_roles"]:
        lines.append(f"### {role['label']}")
        lines.append(f"- Responsibility: {role['responsibility']}")
        lines.append("- Next actions:")
        lines.extend(f"  - {item}" for item in role["next_actions"])
        lines.append("- Evidence needed:")
        lines.extend(f"  - {item}" for item in role["evidence_needed"])
        lines.append("")
    lines.extend(["## Deliverables", ""])
    lines.extend(f"- {item['name']} ({item['owner']}): {item['status']}" for item in package["deliverables"])
    lines.extend(["", "## Approval Boundary", ""])
    if package["risk"]["blocked_actions"]:
        lines.extend(f"- Blocked: {item}" for item in package["risk"]["blocked_actions"])
    else:
        lines.append("- No high-risk blocker detected, but external release still requires configured authorization.")
    lines.append("")
    return "\n".join(lines)
