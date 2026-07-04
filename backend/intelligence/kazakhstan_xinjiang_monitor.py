from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.models import now_iso
from core.storage import read_json, write_json, write_text

DRAFT_NOTICE = "DRAFT - Not approved for sending"

FOCUS_SECTORS = [
    "Kazakhstan five-year and ten-year government plans",
    "mining development and large mine logistics",
    "metallurgy, smelter and steel plant equipment",
    "thermal power stations and coal handling systems",
    "wagon tipplers, stackers, reclaimers, conveyors and unloading lines",
    "Aktau and Kuryk Caspian port construction and cargo handling",
    "oil refining and petrochemical modernization",
    "Xinjiang border port customs and freight monitoring",
    "agricultural machinery, agricultural drones, organic and liquid fertilizer",
]

XINJIANG_PORTS = [
    "Alashankou port",
    "Horgos port",
    "Jeminay port",
    "Yili Prefecture border ports",
    "southern Xinjiang ports",
]

PROJECT_LEADS = [
    {
        "id": "KZ-MIN-001",
        "name": "Kazakhstan mining development and ore logistics watch",
        "country": "Kazakhstan",
        "sector": "mining",
        "status": "screening",
        "opportunity_signal": "Track mine expansion, crushing, hauling, loading, unloading and railway/port links.",
        "feasibility_gate": "Requires official owner, license, reserve, transport route and capex evidence.",
        "human_approval_required": True,
        "external_action_allowed": False,
        "risk_level": "high",
        "evidence_required": ["owner announcement", "license/reserve evidence", "transport route", "capex or tender notice"],
        "search_queries": [
            "site:gov.kz Kazakhstan mining development investment program",
            "site:invest.gov.kz Kazakhstan mining metallurgy project",
            "Kazakhstan mine expansion ore logistics railway port EPC",
        ],
    },
    {
        "id": "KZ-MET-001",
        "name": "Kazakhstan metallurgy and smelter modernization watch",
        "country": "Kazakhstan",
        "sector": "metallurgy",
        "status": "screening",
        "opportunity_signal": "Monitor furnace, raw-material handling, environmental retrofit and steel plant equipment demand.",
        "feasibility_gate": "Requires official investment plan, plant owner confirmation and technical scope.",
        "human_approval_required": True,
        "external_action_allowed": False,
        "risk_level": "high",
        "evidence_required": ["plant owner", "modernization scope", "procurement/tender source", "environmental requirements"],
        "search_queries": [
            "site:gov.kz Kazakhstan metallurgy plant modernization",
            "site:invest.gov.kz Kazakhstan smelter steel plant investment",
            "Kazakhstan furnace raw material handling environmental retrofit",
        ],
    },
    {
        "id": "KZ-PWR-001",
        "name": "Kazakhstan thermal power and coal handling watch",
        "country": "Kazakhstan",
        "sector": "power",
        "status": "screening",
        "opportunity_signal": "Watch generation capacity, coal mine feedstock, wagon tippler, stacker and conveyor packages.",
        "feasibility_gate": "Requires government energy plan, fuel supply route, EPC model and emissions constraints.",
        "human_approval_required": True,
        "external_action_allowed": False,
        "risk_level": "high",
        "evidence_required": ["government energy plan", "plant owner", "fuel supply route", "EPC or procurement model", "emissions constraints"],
        "search_queries": [
            "site:gov.kz Kazakhstan thermal power plant construction",
            "site:primeminister.kz Kazakhstan power plant modernization",
            "Kazakhstan coal handling wagon tippler stacker conveyor power plant",
        ],
    },
    {
        "id": "KZ-CAS-001",
        "name": "Caspian Sea port construction and bulk cargo handling watch",
        "country": "Kazakhstan",
        "sector": "ports",
        "status": "screening",
        "opportunity_signal": "Track Aktau/Kuryk quay, storage yard, lifting, transport and ore loading projects.",
        "feasibility_gate": "Requires port authority source, financing plan, cargo forecast and sanction/compliance check.",
        "human_approval_required": True,
        "external_action_allowed": False,
        "risk_level": "high",
        "evidence_required": ["port authority source", "cargo forecast", "financing plan", "sanctions/compliance review"],
        "search_queries": [
            "site:gov.kz Aktau port development Kazakhstan",
            "site:gov.kz Kuryk port infrastructure Kazakhstan",
            "Kazakhstan Caspian port bulk cargo ore loading equipment",
        ],
    },
    {
        "id": "KZ-OIL-001",
        "name": "Kazakhstan oil refining and petrochemical modernization watch",
        "country": "Kazakhstan",
        "sector": "oil_refining",
        "status": "screening",
        "opportunity_signal": "Monitor refinery upgrade, utilities, storage, loading and environmental equipment packages.",
        "feasibility_gate": "Requires owner announcement, tender evidence, sanctions screen and payment route review.",
        "human_approval_required": True,
        "external_action_allowed": False,
        "risk_level": "high",
        "evidence_required": ["owner announcement", "tender evidence", "technical package", "sanctions screen", "payment route review"],
        "search_queries": [
            "site:gov.kz Kazakhstan oil refinery modernization",
            "site:invest.gov.kz Kazakhstan petrochemical project",
            "Kazakhstan refinery storage loading utilities environmental equipment",
        ],
    },
    {
        "id": "KZ-INF-001",
        "name": "Kazakhstan government infrastructure plan watch",
        "country": "Kazakhstan",
        "sector": "government_infrastructure",
        "status": "screening",
        "opportunity_signal": "Screen five-year and ten-year national, regional and logistics plans for EPC, railway, port, energy and industrial park packages.",
        "feasibility_gate": "Requires official plan text, budget source, procurement route, responsible agency and approval stage.",
        "human_approval_required": True,
        "external_action_allowed": False,
        "risk_level": "high",
        "evidence_required": ["official plan", "budget line", "responsible agency", "procurement route", "approval stage"],
        "search_queries": [
            "site:gov.kz Kazakhstan national infrastructure plan 2030",
            "site:primeminister.kz Kazakhstan infrastructure development plan",
            "Kazakhstan five year ten year plan railway energy port industrial park",
        ],
    },
    {
        "id": "KZ-AGR-001",
        "name": "Kazakhstan agriculture machinery, drone and fertilizer watch",
        "country": "Kazakhstan",
        "sector": "agriculture",
        "status": "screening",
        "opportunity_signal": "Track agricultural machinery, agricultural drones, organic fertilizer, liquid fertilizer and plant/animal growth additive demand.",
        "feasibility_gate": "Requires local registration rules, buyer type, import rules, product compliance and channel evidence.",
        "human_approval_required": True,
        "external_action_allowed": False,
        "risk_level": "medium",
        "evidence_required": ["registration rules", "buyer/channel evidence", "import rules", "product compliance"],
        "search_queries": [
            "site:gov.kz Kazakhstan agricultural machinery subsidy",
            "Kazakhstan agricultural drones fertilizer import demand",
            "Kazakhstan organic fertilizer liquid fertilizer plant growth regulator",
        ],
    },
]

CUSTOMS_FIELDS = [
    "date_period", "port", "customs_district", "trade_mode", "logistics_mode", "hs_code", "commodity", "quantity", "value", "unit_price", "quality_or_grade", "origin", "destination", "source_url", "confidence", "opportunity_signal", "risk_signal",
]

WORK_BUDDY_COLLECTION_MATRIX = [
    {
        "collector": "official_public_pages",
        "cadence": "30min",
        "scope": "government plans, procurement notices, investment agencies, port and energy authorities",
        "allowed_methods": ["public web pages", "RSS", "approved search APIs", "subscribed data APIs"],
        "blocked_methods": ["paywall bypass", "credential sharing", "website vulnerability exploitation", "unauthorized scraping"],
    },
    {
        "collector": "customs_and_port_watch",
        "cadence": "daily",
        "scope": "Alashankou, Horgos, Jeminay, Yili Prefecture ports, southern Xinjiang ports, HS code and freight signals",
        "allowed_methods": ["official customs publications", "approved API", "licensed customs-data provider"],
        "blocked_methods": ["unlicensed database access", "source impersonation", "manual figure fabrication"],
    },
    {
        "collector": "project_feasibility_intake",
        "cadence": "daily",
        "scope": "mining, metallurgy, thermal power, Caspian ports, oil refining, agriculture machinery and fertilizer",
        "allowed_methods": ["evidence dossier", "source grading", "owner/developer/procurement verification"],
        "blocked_methods": ["external commitment before approval", "quotation before human decision", "treating leads as confirmed projects"],
    },
    {
        "collector": "content_draft_pipeline",
        "cadence": "on demand",
        "scope": "internal brief, feasibility draft, video/script draft and social media draft",
        "allowed_methods": ["DRAFT output", "policy check", "human approval queue"],
        "blocked_methods": ["automatic public publishing", "external outreach", "customer reply without approval"],
    },
]

SKILL_ASSESSMENT_ITEMS = [
    "Search expansion quality across Chinese, English, Russian and Kazakhstan/Qazaqstan naming variants",
    "Official-source recognition for government, customs, procurement, port, energy and investment agencies",
    "Feasibility report structure: owner, scope, evidence, economics, logistics, compliance, risks and approval gate",
    "Customs-data discipline: HS code, port, period, quantity, value, grade, origin/destination and source URL",
    "Risk boundary discipline: sanctions, export control, customs conclusion, quotation, payment, contract and public publishing",
]

WORK_BUDDY_SOURCE_NOTES = [
    "Imported planning concepts from Work Buddy docs: collection matrix, market analysis, architecture optimization and social draft pipeline.",
    "Automatic publishing concepts are converted to draft-only internal workflow until human approval.",
    "Cloud or GitHub Actions scheduling is required for operation while the local computer is powered off.",
]


def _today() -> str:
    return datetime.now().date().isoformat()


def _append_audit(root: Path, action: str, result: str, note: str) -> None:
    line = f"{now_iso()} | CODEX | {action} | 86 | MEDIUM | {result} | {note}\n"
    path = root / "memory" / "audit.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _render_daily_log(date: str, summary: dict[str, Any]) -> str:
    matrix = "\n".join(
        f"- {item['collector']} ({item['cadence']}): {item['scope']}"
        for item in summary.get("work_buddy_collection_matrix", [])
    )
    assessments = "\n".join(f"- {item}" for item in summary.get("skill_assessment_items", []))
    return f"""# Kazakhstan and Xinjiang Daily Monitoring Log

{DRAFT_NOTICE}

Generated: {summary["generated_at"]}

## Purpose

Build a daily unattended evidence chain for Kazakhstan project screening, Xinjiang border-port customs monitoring, market signals, and feasibility-report preparation.

## Today's Work

- Maintain Kazakhstan project library for mining, metallurgy, power, Caspian ports, oil refining, agriculture machinery and fertilizer opportunities.
- Maintain Xinjiang customs watch fields for Alashankou, Horgos, Jeminay, Yili Prefecture ports and southern Xinjiang ports.
- Record whether live news/customs APIs are configured before treating figures as current facts.
- Keep all external-use outputs as drafts pending human review.
- Reuse Work Buddy collection matrix for internal source planning, project intake and report drafting.

## Work Buddy Collection Matrix

{matrix}

## Skill Assessment

{assessments}

## Output Chain

- News update: `backend/reports/news_updates/{date}.md`
- Project library report: `backend/reports/project_library/{date}.md`
- Project library database: `backend/projects/library/kazakhstan_xinjiang_projects.json`
- Customs watch snapshot: `backend/memory/monitoring/customs_watch/{date}.json`
"""


def _render_news_update(summary: dict[str, Any]) -> str:
    live = summary["source_status"]
    sectors = "\n".join(f"- {item}" for item in FOCUS_SECTORS)
    notes = "\n".join(f"- {item}" for item in summary.get("work_buddy_source_notes", []))
    return f"""# Kazakhstan / Xinjiang News and Market Update

{DRAFT_NOTICE}

Generated: {summary["generated_at"]}

## Source Status

- Live fetch: {str(live["live_fetch"]).lower()}
- Reason: {live["reason"]}
- Boundary: public, official or subscribed sources only; no unauthorized access or paywall bypass.

## Monitoring Sectors

{sectors}

## Search Expansion

- Kazakhstan / Qazaqstan / Kazakhstan government plan / mining EPC / metallurgy plant / thermal power / Caspian port / Aktau / Kuryk
- Alashankou / Horgos / Jeminay / Yili ports / Xinjiang customs / HS code / railway freight / ore imports / agricultural machinery

## Analyst Note

Today's v11 chain creates the report and database even when no live feed is configured. Real-time statistics must come from official customs publications, subscribed customs-data providers, or approved APIs.

## Work Buddy Integration Notes

{notes}
"""


def _render_project_library(date: str, projects: list[dict[str, Any]]) -> str:
    lines = ["# Kazakhstan Project Library", "", DRAFT_NOTICE, "", f"Date: {date}", ""]
    for project in projects:
        lines.extend([
            f"## {project['id']} - {project['name']}", "",
            f"- Country: {project['country']}", f"- Sector: {project['sector']}", f"- Status: {project['status']}",
            f"- Opportunity signal: {project['opportunity_signal']}", f"- Feasibility gate: {project['feasibility_gate']}",
            f"- Human approval required: {project['human_approval_required']}",
            f"- External action allowed: {project.get('external_action_allowed', False)}",
            f"- Risk level: {project.get('risk_level', 'high')}",
            f"- Evidence required: {', '.join(project.get('evidence_required', [])) or 'official confirmation required'}",
            "- Search queries:",
            *[f"  - {query}" for query in project.get("search_queries", [])],
            "",
        ])
    return "\n".join(lines)


def build_monitoring_summary(root: Path) -> dict[str, Any]:
    date = _today()
    generated_at = now_iso()
    source_status = {
        "live_fetch": False,
        "reason": "No authorized live news/customs/customs-data API is configured",
        "allowed_sources": ["official public pages", "subscribed data APIs", "approved search APIs"],
        "blocked_sources": ["unauthorized access", "paywall bypass", "website vulnerability exploitation"],
    }
    customs_watch = {
        "date": date,
        "generated_at": generated_at,
        "ports": XINJIANG_PORTS,
        "required_fields": CUSTOMS_FIELDS,
        "records": [],
        "source_status": source_status,
        "work_buddy_collection_matrix": WORK_BUDDY_COLLECTION_MATRIX,
        "next_action": "Configure official customs publication source, approved crawler, or subscribed customs-data API before daily volume statistics are treated as factual.",
    }
    project_db_path = root / "projects" / "library" / "kazakhstan_xinjiang_projects.json"
    existing = read_json(project_db_path, {})
    existing_projects = {item.get("id"): item for item in existing.get("projects", []) if item.get("id")}
    for lead in PROJECT_LEADS:
        existing_projects[lead["id"]] = {**lead, "updated_at": generated_at}
    project_library = {
        "generated_at": generated_at,
        "draft_notice": DRAFT_NOTICE,
        "source_status": source_status,
        "projects": list(existing_projects.values()),
        "customs_watch_fields": CUSTOMS_FIELDS,
        "focus_ports": XINJIANG_PORTS,
        "work_buddy_collection_matrix": WORK_BUDDY_COLLECTION_MATRIX,
        "skill_assessment_items": SKILL_ASSESSMENT_ITEMS,
        "publication_policy": {
            "mode": "draft_only",
            "external_publish_allowed": False,
            "human_approval_required_for": [
                "public publishing",
                "external outreach",
                "quotation",
                "payment",
                "contract",
                "customs conclusion",
                "government or infrastructure commitment",
            ],
        },
    }
    summary = {
        "generated_at": generated_at,
        "date": date,
        "draft_notice": DRAFT_NOTICE,
        "source_status": source_status,
        "project_count": len(project_library["projects"]),
        "customs_port_count": len(XINJIANG_PORTS),
        "focus_sectors": FOCUS_SECTORS,
        "work_buddy_collection_matrix": WORK_BUDDY_COLLECTION_MATRIX,
        "skill_assessment_items": SKILL_ASSESSMENT_ITEMS,
        "work_buddy_source_notes": WORK_BUDDY_SOURCE_NOTES,
        "publication_policy": project_library["publication_policy"],
        "artifacts": {
            "daily_log": str(root / "reports" / "daily_logs" / f"{date}.md"),
            "news_update_markdown": str(root / "reports" / "news_updates" / f"{date}.md"),
            "news_update_json": str(root / "reports" / "news_updates" / f"{date}.json"),
            "project_library_report": str(root / "reports" / "project_library" / f"{date}.md"),
            "project_library_database": str(project_db_path),
            "customs_watch": str(root / "memory" / "monitoring" / "customs_watch" / f"{date}.json"),
            "latest_summary": str(root / "memory" / "monitoring" / "kazakhstan_xinjiang_daily.json"),
            "overview_report": str(root / "reports" / "kazakhstan_xinjiang_monitoring.md"),
        },
    }
    write_text(root / "reports" / "daily_logs" / f"{date}.md", _render_daily_log(date, summary))
    write_text(root / "reports" / "news_updates" / f"{date}.md", _render_news_update(summary))
    write_json(root / "reports" / "news_updates" / f"{date}.json", summary)
    write_text(root / "reports" / "project_library" / f"{date}.md", _render_project_library(date, project_library["projects"]))
    write_json(project_db_path, project_library)
    write_json(root / "memory" / "monitoring" / "customs_watch" / f"{date}.json", customs_watch)
    write_json(root / "memory" / "monitoring" / "kazakhstan_xinjiang_daily.json", summary)
    write_text(root / "reports" / "kazakhstan_xinjiang_monitoring.md", _render_news_update(summary))
    _append_audit(root, "KAZAKHSTAN_XINJIANG_DAILY_MONITOR", "completed", "daily log, news update, project library and customs watch artifacts refreshed")
    return summary
