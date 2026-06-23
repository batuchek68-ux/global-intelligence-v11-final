from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

from backend.services.audit_service import append_audit
from backend.services.evidence_verification_service import build_evidence_dossier
from backend.services.project_action_board_service import build_and_write_action_board
from backend.services.search_service import enrich_query


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_LIBRARY_DIR = BACKEND_ROOT / "memory" / "project_library"
PROJECT_LIBRARY_PATH = PROJECT_LIBRARY_DIR / "projects.json"
FEASIBILITY_DIR = BACKEND_ROOT / "reports" / "feasibility"

GOVERNMENT_DOMAINS_BY_COUNTRY = {
    "kazakhstan": [
        "gov.kz",
        "primeminister.kz",
        "invest.gov.kz",
        "adilet.zan.kz",
        "goszakup.gov.kz",
        "sk.kz",
    ],
    "central asia": [
        "gov.kz",
        "gov.uz",
        "gov.kg",
        "gov.tm",
        "tajinvest.tj",
    ],
}

UNDER_CONSTRUCTION_KEYWORDS = [
    "under construction",
    "construction started",
    "construction began",
    "works commenced",
    "contract awarded",
    "contract signed",
    "site works",
    "施工",
    "开工",
    "在建",
    "建设中",
    "已开工",
    "строительство",
    "строится",
]

PLANNED_KEYWORDS = [
    "planned",
    "proposed",
    "feasibility study",
    "pre-feasibility",
    "tender announced",
    "eia",
    "public hearing",
    "investment project",
    "拟建",
    "计划建设",
    "规划",
    "可研",
    "招标",
    "планируется",
    "проект",
]

ROLE_PATTERNS = {
    "project_owner": ["owner", "client", "заказчик", "业主", "项目业主"],
    "developer": ["developer", "investor", "sponsor", "разработчик", "投资方", "开发商"],
    "government_authority": ["ministry", "akimat", "agency", "department", "gov", "部", "政府", "委员会"],
    "contractor": ["contractor", "epc", "construction company", "承包商", "总包", "施工单位"],
    "contact_person": ["project manager", "contact person", "responsible person", "负责人", "联系人"],
}

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_library_path() -> Path:
    override = os.getenv("V11_PROJECT_LIBRARY_PATH")
    return Path(override) if override else PROJECT_LIBRARY_PATH


def _feasibility_dir() -> Path:
    override = os.getenv("V11_FEASIBILITY_DIR")
    return Path(override) if override else FEASIBILITY_DIR


def _stable_id(*parts: str) -> str:
    raw = "|".join(part.strip().lower() for part in parts if part)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _is_government_source(url: str, source_type: str = "", country: str = "") -> bool:
    domain = _domain(url)
    if source_type.lower() in {"government", "official", "gov"}:
        return True
    country_key = country.strip().lower()
    domains = GOVERNMENT_DOMAINS_BY_COUNTRY.get(country_key, []) + GOVERNMENT_DOMAINS_BY_COUNTRY["central asia"]
    return any(domain == item or domain.endswith(f".{item}") for item in domains)


def _search_url(engine: str, query: str) -> str:
    encoded = quote_plus(query)
    if engine == "google":
        return f"https://www.google.com/search?q={encoded}"
    if engine == "yandex":
        return f"https://yandex.com/search/?text={encoded}"
    return f"https://www.bing.com/search?q={encoded}"


def build_project_search_plan(topic: str, country: str = "Kazakhstan") -> dict[str, Any]:
    enriched = enrich_query(topic)
    country_key = country.lower()
    official_domains = GOVERNMENT_DOMAINS_BY_COUNTRY.get(country_key, GOVERNMENT_DOMAINS_BY_COUNTRY["central asia"])
    base_queries = enriched["queries"][:8] or [topic]
    intent_templates = [
        "{q} site:{domain}",
        "{q} project owner developer government",
        "{q} tender procurement EPC contractor",
        "{q} feasibility study EIA public hearing",
        "{q} investor developer financing",
        "{q} responsible person project manager contact",
    ]

    queries: list[dict[str, Any]] = []
    for base in base_queries:
        for domain in official_domains[:4]:
            official_query = intent_templates[0].format(q=base, domain=domain)
            queries.append(
                {
                    "intent": "government_confirmation",
                    "query": official_query,
                    "priority": "highest",
                    "urls": {
                        "google": _search_url("google", official_query),
                        "yandex": _search_url("yandex", official_query),
                        "bing": _search_url("bing", official_query),
                    },
                }
            )
        for template in intent_templates[1:]:
            query = template.format(q=base, domain="")
            queries.append(
                {
                    "intent": "project_development_intelligence",
                    "query": query,
                    "priority": "normal",
                    "urls": {
                        "google": _search_url("google", query),
                        "yandex": _search_url("yandex", query),
                        "bing": _search_url("bing", query),
                    },
                }
            )

    return {
        "topic": topic,
        "country": country,
        "official_domains": official_domains,
        "enrichment": enriched,
        "queries": queries[:60],
        "collection_rules": [
            "Prefer government and official procurement pages before media or social sources.",
            "Classify projects as under_construction only when source text shows work started, contract awarded, or construction in progress.",
            "Classify projects as planned when source text shows planning, feasibility, EIA, public hearing, tender, or investment proposal.",
            "Do not mark a responsible person as confirmed unless the evidence source names the person or office.",
        ],
    }


def classify_project_stage(text: str) -> dict[str, Any]:
    lower = text.lower()
    under_hits = [item for item in UNDER_CONSTRUCTION_KEYWORDS if item.lower() in lower]
    planned_hits = [item for item in PLANNED_KEYWORDS if item.lower() in lower]
    if under_hits:
        return {"category": "under_construction", "label": "在建项目", "evidence": under_hits[:5]}
    if planned_hits:
        return {"category": "planned", "label": "计划建设项目", "evidence": planned_hits[:5]}
    return {"category": "unknown", "label": "待确认项目", "evidence": []}


def extract_stakeholders(text: str) -> dict[str, list[str]]:
    stakeholders: dict[str, list[str]] = {role: [] for role in ROLE_PATTERNS}
    lines = [line.strip() for line in re.split(r"[\n\r.;。；]", text) if line.strip()]
    for line in lines:
        line_lower = line.lower()
        for role, keywords in ROLE_PATTERNS.items():
            if any(keyword.lower() in line_lower for keyword in keywords):
                cleaned = re.sub(r"\s+", " ", line)[:220]
                if cleaned not in stakeholders[role]:
                    stakeholders[role].append(cleaned)
    return {role: values[:8] for role, values in stakeholders.items() if values}


def _normalize_evidence_items(evidence_items: list[dict[str, Any]], country: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in evidence_items:
        title = str(item.get("title") or item.get("name") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("snippet") or item.get("summary") or item.get("text") or "").strip()
        source_type = str(item.get("source_type") or item.get("source") or "").strip()
        normalized.append(
            {
                "title": title,
                "url": url,
                "domain": _domain(url) if url else "",
                "snippet": snippet,
                "source_type": source_type,
                "government_confirmed": _is_government_source(url, source_type, country) if url else source_type.lower() in {"government", "official", "gov"},
                "collected_at": item.get("collected_at") or _now_iso(),
            }
        )
    return normalized


def assess_promotion_readiness(record: dict[str, Any]) -> dict[str, Any]:
    """Classify whether a project can move from lead to investment-promotion work."""
    confirmation = str(record.get("confirmation_level") or "")
    confidence = int(record.get("confidence") or 0)
    category = str(record.get("category") or "")
    has_official = bool(record.get("government_sources"))
    has_owner = bool(record.get("owner_candidates"))
    has_developer = bool(record.get("developer_candidates"))
    reasons: list[str] = []

    if not has_official:
        reasons.append("缺少政府、采购、海关、监管或官方企业证据。")
    if category not in {"planned", "under_construction"}:
        reasons.append("项目阶段尚未确认，不能判断为计划建设或在建项目。")
    if confidence < 90:
        reasons.append("置信度低于 90，不能进入招商材料草稿。")
    if not has_owner:
        reasons.append("业主或主管部门候选尚未确认。")
    if not has_developer:
        reasons.append("开发者、投资方或承包商候选尚未确认。")

    if confirmation == "government_confirmed" and confidence >= 90 and category in {"planned", "under_construction"}:
        if has_owner and has_developer:
            status = "draft_promotion_ready"
            label = "可生成招商草稿"
            allowed_internal_actions = [
                "生成内部招商引资草稿",
                "生成可行性报告草稿",
                "进入高价值项目关注清单",
                "准备人工审批包",
            ]
        else:
            status = "internal_screening_ready"
            label = "可内部筛选"
            allowed_internal_actions = [
                "进入项目库内部筛选",
                "继续补业主、开发者、投资方和负责人证据",
                "生成内部尽调任务板",
            ]
    elif confirmation == "government_confirmed":
        status = "evidence_review_required"
        label = "需补证据"
        allowed_internal_actions = [
            "保留为内部项目线索",
            "补充阶段、业主、开发者、海关和采购证据",
        ]
    else:
        status = "lead_only"
        label = "仅线索"
        allowed_internal_actions = [
            "只允许内部搜索和证据收集",
            "不得作为招商引资项目使用",
        ]

    return {
        "status": status,
        "label": label,
        "can_create_lead_record": True,
        "can_generate_internal_promotion_draft": status == "draft_promotion_ready",
        "approved_for_external_use": False,
        "human_approval_required_for_external_use": True,
        "allowed_internal_actions": allowed_internal_actions,
        "blocked_actions": [
            "正式招商发布",
            "客户或投资人外联",
            "报价",
            "合同或付款承诺",
            "交期或清关承诺",
            "公开视频发布",
        ],
        "missing_requirements": reasons,
    }


def build_project_record(topic: str, country: str, evidence_items: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = _normalize_evidence_items(evidence_items, country)
    combined_text = " ".join([topic, country] + [f"{item['title']} {item['snippet']}" for item in evidence])
    stage = classify_project_stage(combined_text)
    stakeholders = extract_stakeholders(combined_text)
    government_sources = [item for item in evidence if item["government_confirmed"]]
    title = next((item["title"] for item in evidence if item["title"]), topic)
    confidence = 85 if government_sources else 55
    if stage["category"] != "unknown":
        confidence += 8
    if stakeholders:
        confidence += 5

    record = {
        "id": _stable_id(country, title, topic),
        "title": title,
        "topic": topic,
        "country": country,
        "category": stage["category"],
        "category_label": stage["label"],
        "status_evidence": stage["evidence"],
        "confirmation_level": "government_confirmed" if government_sources else "unverified_or_secondary",
        "confidence": min(confidence, 98),
        "government_sources": government_sources,
        "evidence": evidence,
        "stakeholders": stakeholders,
        "owner_candidates": stakeholders.get("project_owner", []) + stakeholders.get("government_authority", []),
        "developer_candidates": stakeholders.get("developer", []),
        "responsible_person_candidates": stakeholders.get("contact_person", []),
        "risk_flags": [
            "Human approval required before external outreach, quotation, commitment, or publication.",
            "Government source confirmation required before investment promotion use.",
        ],
        "updated_at": _now_iso(),
    }
    record["promotion_readiness"] = assess_promotion_readiness(record)
    return record


def read_project_library(path: Path | None = None) -> dict[str, Any]:
    target = path or _project_library_path()
    if not target.exists():
        return _summarize_project_library([], target)
    try:
        projects = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(projects, list):
            projects = []
    except json.JSONDecodeError:
        projects = []
    return _summarize_project_library(projects, target)


def _summarize_project_library(projects: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    buckets = {
        "under_construction": [],
        "planned": [],
        "unconfirmed": [],
    }
    for project in projects:
        if not isinstance(project, dict):
            continue
        category = str(project.get("category") or "")
        if category == "under_construction":
            buckets["under_construction"].append(project)
        elif category == "planned":
            buckets["planned"].append(project)
        else:
            buckets["unconfirmed"].append(project)

    official_ready = [
        project
        for project in projects
        if isinstance(project, dict)
        and project.get("confirmation_level") == "government_confirmed"
        and int(project.get("confidence") or 0) >= 90
    ]
    needs_evidence = [
        project
        for project in projects
        if isinstance(project, dict)
        and (
            project.get("confirmation_level") != "government_confirmed"
            or int(project.get("confidence") or 0) < 90
        )
    ]
    high_value_watchlist = sorted(
        [project for project in projects if isinstance(project, dict)],
        key=lambda item: (
            item.get("confirmation_level") == "government_confirmed",
            int(item.get("confidence") or 0),
            bool(item.get("owner_candidates")),
            bool(item.get("developer_candidates")),
        ),
        reverse=True,
    )[:20]
    promotion_buckets = {
        "lead_only": [],
        "evidence_review_required": [],
        "internal_screening_ready": [],
        "draft_promotion_ready": [],
    }
    for project in projects:
        if not isinstance(project, dict):
            continue
        readiness = project.get("promotion_readiness")
        if not isinstance(readiness, dict):
            readiness = assess_promotion_readiness(project)
            project["promotion_readiness"] = readiness
        status = str(readiness.get("status") or "lead_only")
        promotion_buckets.setdefault(status, []).append(project)

    return {
        "ok": True,
        "path": str(path),
        "projects": projects,
        "summary": {
            "total": len(projects),
            "under_construction": len(buckets["under_construction"]),
            "planned": len(buckets["planned"]),
            "unconfirmed": len(buckets["unconfirmed"]),
            "official_ready": len(official_ready),
            "needs_evidence": len(needs_evidence),
            "promotion_draft_ready": len(promotion_buckets["draft_promotion_ready"]),
            "internal_screening_ready": len(promotion_buckets["internal_screening_ready"]),
            "lead_only": len(promotion_buckets["lead_only"]),
        },
        "categories": buckets,
        "promotion_buckets": promotion_buckets,
        "official_ready": official_ready,
        "needs_evidence": needs_evidence,
        "high_value_watchlist": high_value_watchlist,
        "rules": [
            "Use official government, customs, procurement, regulator, or official company evidence before promotion.",
            "Classify under_construction only when evidence shows started works, site activity, or contract award.",
            "Classify planned only when evidence shows planning, feasibility, EIA, public hearing, tender, or investment proposal.",
            "External outreach, quotation, contract, payment, and public publication still require human approval.",
        ],
    }


def upsert_project_record(record: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    target = path or _project_library_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    library = read_project_library(target)["projects"]
    replaced = False
    updated = []
    for existing in library:
        if existing.get("id") == record["id"]:
            updated.append(record)
            replaced = True
        else:
            updated.append(existing)
    if not replaced:
        updated.append(record)
    target.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    append_audit(
        "PROJECT_LIBRARY_UPSERT",
        "DONE",
        f"Project={record.get('title')} category={record.get('category')} confirmation={record.get('confirmation_level')}",
        confidence=int(record.get("confidence", 70)),
        risk="MEDIUM",
    )
    return {"ok": True, "path": str(target), "project": record, "created": not replaced}


def discover_projects(topic: str, country: str = "Kazakhstan", evidence_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    plan = build_project_search_plan(topic, country)
    evidence = evidence_items or []
    records = []
    if evidence:
        record = build_project_record(topic, country, evidence)
        upsert_project_record(record)
        records.append(record)

    return {
        "ok": True,
        "topic": topic,
        "country": country,
        "search_plan": plan,
        "records_created": len(records),
        "projects": records,
        "next_actions": [
            "Open the highest-priority government search URLs and collect official project evidence.",
            "Add evidence items with title, url, snippet, and source_type=government to confirm projects.",
            "Use /v1/reports/feasibility after government evidence is attached.",
        ],
    }


def build_project_pipeline(
    topic: str,
    country: str = "Kazakhstan",
    evidence_items: list[dict[str, Any]] | None = None,
    *,
    persist: bool = True,
) -> dict[str, Any]:
    """Turn search/evidence into a project-library and execution package.

    This is the bridge from intelligence search to project execution: search
    plan, evidence dossier, project record, action board, feasibility draft, and
    approval boundary in one response.
    """
    evidence_items = evidence_items or []
    search_plan = build_project_search_plan(topic, country)
    dossier = build_evidence_dossier(topic, evidence_items, project=topic, country=country)
    project = build_project_record(topic, country, evidence_items) if evidence_items else {
        "id": _stable_id(country, topic),
        "title": topic,
        "topic": topic,
        "country": country,
        "category": "unconfirmed_pipeline",
        "category_label": "待证据确认项目",
        "confirmation_level": "search_plan_only",
        "confidence": 30,
        "government_sources": [],
        "evidence": [],
        "stakeholders": {},
        "owner_candidates": [],
        "developer_candidates": [],
        "responsible_person_candidates": [],
        "risk_flags": [
            "No official evidence attached yet.",
            "Only search planning and internal tasking are allowed.",
        ],
        "updated_at": _now_iso(),
    }
    if "promotion_readiness" not in project:
        project["promotion_readiness"] = assess_promotion_readiness(project)

    if persist and evidence_items:
        upsert_project_record(project)

    case = {
        "created_at": _now_iso(),
        "project": {
            "title": project["title"],
            "country": country,
            "stage": project["category"],
            "next_decision": "Approve evidence-based outreach or continue research?",
        },
        "classification": {
            "is_major_matter": dossier.get("requires_human_review", True)
            or project.get("confirmation_level") != "government_confirmed"
            or project.get("confidence", 0) < 90,
        },
        "judgment": {
            "level": "high" if dossier.get("requires_human_review", True) else "medium",
            "score": 90 if dossier.get("requires_human_review", True) else 60,
            "triggers": dossier.get("high_risk_terms", []) or ["project_confirmation", "external_outreach"],
        },
    }
    action_board_result = build_and_write_action_board(case, dossier) if persist else {"ok": True, "board": None}
    feasibility = build_feasibility_report(project) if persist else {
        "ok": True,
        "approved_for_sending": False,
        "content": "DRAFT - Not approved for sending",
    }

    result = {
        "ok": True,
        "mode": "project_intelligence_pipeline",
        "topic": topic,
        "country": country,
        "search_plan": search_plan,
        "evidence_dossier": dossier,
        "project": project,
        "project_library": {
            "updated": bool(persist and evidence_items),
            "path": str(_project_library_path()),
            "rule": "Project records become promotion-ready only after official evidence and human approval.",
        },
        "promotion_readiness": project["promotion_readiness"],
        "action_board": action_board_result.get("board"),
        "feasibility_report": {
            "ok": feasibility.get("ok", False),
            "path": feasibility.get("path"),
            "approved_for_sending": False,
        },
        "blocked_actions": [
            "external outreach",
            "formal investment promotion publication",
            "quotation",
            "contract or payment commitment",
            "public video publication",
        ],
        "next_actions": [
            "Open official government and procurement search URLs from the highest priority plan.",
            "Attach official evidence with title, URL, snippet, source_type, and source date.",
            "Confirm project owner, developer, responsible office/person, tender status, and customs impact.",
            "Use the action board for team task assignment.",
            "Request human approval before any external message or publication.",
        ],
    }
    append_audit(
        "PROJECT_INTELLIGENCE_PIPELINE_BUILT",
        "DONE",
        f"Built pipeline for {topic}; confirmation={project.get('confirmation_level')}; evidence={len(evidence_items)}.",
        confidence=int(project.get("confidence", 70) or 70),
        risk="MEDIUM",
    )
    return result


def build_feasibility_report(project: dict[str, Any]) -> dict[str, Any]:
    title = str(project.get("title") or project.get("topic") or "Untitled project")
    project_id = str(project.get("id") or _stable_id(title))
    government_sources = project.get("government_sources") or []
    stakeholders = project.get("stakeholders") or {}
    promotion = project.get("promotion_readiness")
    if not isinstance(promotion, dict):
        promotion = assess_promotion_readiness(project)
    lines = [
        f"# Feasibility Report Draft: {title}",
        "",
        "DRAFT - Not approved for sending",
        "",
        "## Authority Level",
        "",
        f"- Confirmation: {project.get('confirmation_level', 'unverified_or_secondary')}",
        f"- Confidence: {project.get('confidence', 0)}",
        f"- Category: {project.get('category_label', project.get('category', 'unknown'))}",
        f"- Promotion readiness: {promotion.get('label')} ({promotion.get('status')})",
        f"- External use approved: {promotion.get('approved_for_external_use')}",
        "",
        "## Government Evidence",
        "",
    ]
    if government_sources:
        for source in government_sources:
            lines.append(f"- {source.get('title') or source.get('domain')}: {source.get('url')}")
    else:
        lines.append("- No government source confirmed yet. Do not use for formal investment promotion.")

    lines.extend(["", "## Stakeholders", ""])
    if stakeholders:
        for role, values in stakeholders.items():
            lines.append(f"- {role}: {'; '.join(values[:4])}")
    else:
        lines.append("- Stakeholders not confirmed.")

    lines.extend(
        [
            "",
            "## Investment Promotion Use",
            "",
            f"- Internal promotion draft: {promotion.get('can_generate_internal_promotion_draft')}.",
            "- Suitable for external招商引资 material only after official evidence and human approval.",
            "- Formal outreach, quotations, commitments, contracts, and public publication are blocked until approval.",
            "",
            "## Recommended Next Steps",
            "",
            "- Confirm project owner and responsible department from official government pages.",
            "- Confirm developer, contractor, tender status, financing model, and land/EIA approvals.",
            "- Create a human approval ticket before contacting any counterparty.",
        ]
    )
    report_dir = _feasibility_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"{project_id}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    append_audit(
        "FEASIBILITY_REPORT_DRAFT",
        "DONE",
        f"Generated feasibility report draft for {title}; not approved for sending.",
        confidence=int(project.get("confidence", 70) or 70),
        risk="MEDIUM",
    )
    return {"ok": True, "path": str(path), "content": "\n".join(lines), "approved_for_sending": False}


