from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.services.audit_service import append_audit


BACKEND_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_MEMORY_DIR = BACKEND_ROOT / "memory" / "evidence"
EVIDENCE_REPORT_DIR = BACKEND_ROOT / "reports" / "evidence"

SOURCE_TIERS = {
    "government": {"tier": 1, "label": "Official government", "base_score": 95},
    "customs": {"tier": 1, "label": "Customs authority", "base_score": 96},
    "procurement": {"tier": 1, "label": "Official procurement", "base_score": 94},
    "regulator": {"tier": 1, "label": "Regulator", "base_score": 93},
    "official_company": {"tier": 2, "label": "Official company", "base_score": 82},
    "academic": {"tier": 2, "label": "Academic or library", "base_score": 78},
    "reputable_news": {"tier": 3, "label": "Reputable media", "base_score": 66},
    "social": {"tier": 4, "label": "Social or forum signal", "base_score": 45},
    "video": {"tier": 4, "label": "Video signal", "base_score": 43},
    "unknown": {"tier": 5, "label": "Unclassified", "base_score": 30},
}

OFFICIAL_DOMAIN_HINTS = [
    "gov.",
    ".gov",
    "customs",
    "goszakup",
    "procurement",
    "tender",
    "invest.gov",
    "primeminister",
    "ministry",
]

HIGH_RISK_FACTS = [
    "contract",
    "payment",
    "price",
    "delivery",
    "customs",
    "tariff",
    "hs code",
    "sanction",
    "export control",
    "government approval",
    "public commitment",
    "合同",
    "付款",
    "报价",
    "交期",
    "海关",
    "关税",
    "制裁",
    "出口管制",
    "政府审批",
    "公开承诺",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory_dir() -> Path:
    override = os.getenv("V11_EVIDENCE_MEMORY_DIR")
    return Path(override) if override else EVIDENCE_MEMORY_DIR


def _report_dir() -> Path:
    override = os.getenv("V11_EVIDENCE_REPORT_DIR")
    return Path(override) if override else EVIDENCE_REPORT_DIR


def _stable_id(*parts: str) -> str:
    raw = "|".join(str(part).strip().lower() for part in parts if part)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _domain(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def infer_source_type(item: dict[str, Any]) -> str:
    if not isinstance(item, dict):
        return "unknown"
    explicit = str(item.get("source_type") or item.get("source") or "").strip().lower()
    if explicit in SOURCE_TIERS:
        return explicit
    url = str(item.get("url") or "").lower()
    domain = _domain(url)
    text = " ".join(str(item.get(field, "")) for field in ("title", "snippet", "summary", "content")).lower()
    combined = f"{url} {domain} {text}"
    if any(hint in combined for hint in ["customs", "海关", "关税", "hs code", "清关", "报关"]):
        return "customs"
    if any(hint in combined for hint in ["procurement", "tender", "goszakup", "招标", "采购", "中标"]):
        return "procurement"
    if any(hint in combined for hint in OFFICIAL_DOMAIN_HINTS):
        return "government"
    if any(hint in combined for hint in ["youtube", "tiktok", "douyin", "video", "视频", "抖音"]):
        return "video"
    if any(hint in combined for hint in ["telegram", "reddit", "forum", "wechat", "linkedin", "social", "论坛", "微信", "社交"]):
        return "social"
    if any(hint in combined for hint in ["scholar", "library", "paper", "university", "journal", "论文", "图书馆", "期刊", "大学"]):
        return "academic"
    if any(hint in combined for hint in ["reuters", "bloomberg", "apnews", "bbc", "financial times"]):
        return "reputable_news"
    if domain and not any(hint in domain for hint in ["google", "bing", "yandex"]):
        return "official_company"
    return "unknown"


def score_evidence_item(item: dict[str, Any], claim: str = "") -> dict[str, Any]:
    item = item if isinstance(item, dict) else {}
    source_type = infer_source_type(item)
    tier = SOURCE_TIERS[source_type]
    title = str(item.get("title") or "")
    url = str(item.get("url") or "")
    snippet = str(item.get("snippet") or item.get("summary") or item.get("content") or "")
    text = f"{claim} {title} {snippet}".lower()
    score = tier["base_score"]
    if url:
        score += 3
    if str(item.get("published_at") or item.get("date") or item.get("collected_at") or ""):
        score += 2
    if claim and any(token in text for token in claim.lower().split()[:8]):
        score += 3
    high_risk_hits = [term for term in HIGH_RISK_FACTS if term.lower() in text]
    if source_type in {"social", "video", "unknown"} and high_risk_hits:
        score -= 12
    return {
        "title": title,
        "url": url,
        "domain": _domain(url),
        "source_type": source_type,
        "source_label": tier["label"],
        "tier": tier["tier"],
        "score": max(0, min(100, score)),
        "snippet": snippet[:600],
        "high_risk_hits": high_risk_hits,
        "collected_at": item.get("collected_at") or _now_iso(),
    }


def build_evidence_dossier(
    claim: str,
    evidence_items: list[dict[str, Any]] | None = None,
    *,
    project: str = "",
    country: str = "Kazakhstan",
) -> dict[str, Any]:
    evidence_items = [item for item in (evidence_items or []) if isinstance(item, dict)]
    scored = [score_evidence_item(item, claim) for item in evidence_items]
    scored.sort(key=lambda item: (item["tier"], -item["score"]))
    official = [item for item in scored if item["tier"] == 1]
    tier2 = [item for item in scored if item["tier"] == 2]
    weak = [item for item in scored if item["tier"] >= 4]
    high_risk_terms = sorted({term for item in scored for term in item["high_risk_hits"]})

    if official:
        verification_status = "officially_supported"
        confidence = min(98, round(sum(item["score"] for item in official[:3]) / min(3, len(official))))
    elif tier2:
        verification_status = "partially_supported"
        confidence = min(84, round(sum(item["score"] for item in tier2[:3]) / min(3, len(tier2))))
    elif scored:
        verification_status = "weak_signal_only"
        confidence = min(59, round(sum(item["score"] for item in scored[:3]) / min(3, len(scored))))
    else:
        verification_status = "unverified"
        confidence = 0

    requires_human_review = bool(high_risk_terms) or verification_status in {"weak_signal_only", "unverified"}
    dossier_id = _stable_id(country, project, claim)
    return {
        "ok": True,
        "id": dossier_id,
        "created_at": _now_iso(),
        "project": project,
        "country": country,
        "claim": claim,
        "verification_status": verification_status,
        "confidence": confidence,
        "requires_human_review": requires_human_review,
        "summary": {
            "total_evidence": len(scored),
            "official_sources": len(official),
            "tier2_sources": len(tier2),
            "weak_signals": len(weak),
            "high_risk_terms": high_risk_terms,
        },
        "evidence": scored,
        "decision_rule": (
            "Official government/customs/procurement evidence is required before project confirmation, "
            "investment promotion, quotation, customer commitment, or public publishing."
        ),
        "next_verification_steps": build_next_verification_steps(claim, country, verification_status),
        "blocked_actions": [
            "formal outreach",
            "investment promotion publication",
            "quotation",
            "contract or payment approval",
            "delivery or customs commitment",
        ] if requires_human_review else ["external publishing still requires configured human approval"],
    }


def build_next_verification_steps(claim: str, country: str, status: str) -> list[dict[str, Any]]:
    base = claim or "project evidence"
    steps = [
        {
            "source": "government",
            "query": f"{country} {base} official government project owner",
            "reason": "Confirm project existence, owner, authority, and status from official pages.",
        },
        {
            "source": "customs",
            "query": f"{country} customs HS code tariff import documents {base}",
            "reason": "Confirm customs, tariff, import license, clearance documents, and export-control assumptions.",
        },
        {
            "source": "procurement",
            "query": f"{country} {base} tender procurement EPC contractor",
            "reason": "Confirm procurement stage, award, contractor, and deadlines.",
        },
        {
            "source": "company",
            "query": f"{base} developer investor official announcement",
            "reason": "Cross-check developer/investor facts with official company disclosures.",
        },
    ]
    if status in {"officially_supported", "partially_supported"}:
        steps.append(
            {
                "source": "human_review",
                "query": "owner approval required before external action",
                "reason": "Ask human owner to approve outreach, publication, quotation, or commitment.",
            }
        )
    return steps


def render_evidence_dossier(dossier: dict[str, Any]) -> str:
    lines = [
        f"# Evidence Verification Dossier: {dossier.get('claim')}",
        "",
        "DRAFT - internal verification record, not approved for external sending",
        "",
        f"- Project: {dossier.get('project') or 'N/A'}",
        f"- Country: {dossier.get('country')}",
        f"- Status: {dossier.get('verification_status')}",
        f"- Confidence: {dossier.get('confidence')}",
        f"- Human review required: {dossier.get('requires_human_review')}",
        "",
        "## Evidence Summary",
        "",
    ]
    summary = dossier.get("summary", {})
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Evidence Items", ""])
    if dossier.get("evidence"):
        for item in dossier["evidence"]:
            lines.append(f"- T{item['tier']} | {item['score']} | {item['source_label']} | {item.get('title') or item.get('domain')}")
            if item.get("url"):
                lines.append(f"  {item['url']}")
    else:
        lines.append("- No evidence attached.")
    lines.extend(["", "## Next Verification Steps", ""])
    for step in dossier.get("next_verification_steps", []):
        lines.append(f"- {step['source']}: {step['query']} | {step['reason']}")
    lines.extend(["", "## Blocked Actions", ""])
    lines.extend(f"- {item}" for item in dossier.get("blocked_actions", []))
    lines.append("")
    return "\n".join(lines)


def write_evidence_dossier(dossier: dict[str, Any]) -> dict[str, Any]:
    memory_dir = _memory_dir()
    report_dir = _report_dir()
    memory_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = memory_dir / f"{dossier['id']}.json"
    report_path = report_dir / f"{dossier['id']}.md"
    latest_json = memory_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    json_text = json.dumps(dossier, ensure_ascii=False, indent=2)
    report_text = render_evidence_dossier(dossier)
    json_path.write_text(json_text, encoding="utf-8")
    report_path.write_text(report_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(report_text, encoding="utf-8")
    append_audit(
        "EVIDENCE_DOSSIER_WRITTEN",
        "DONE",
        f"Evidence dossier id={dossier['id']} status={dossier['verification_status']} confidence={dossier['confidence']}",
        confidence=max(70, int(dossier.get("confidence", 70) or 70)),
        risk="MEDIUM" if dossier.get("requires_human_review") else "LOW",
    )
    return {"ok": True, "dossier": dossier, "json_path": str(json_path), "report_path": str(report_path)}


def verify_claim(
    claim: str,
    evidence_items: list[dict[str, Any]] | None = None,
    *,
    project: str = "",
    country: str = "Kazakhstan",
    persist: bool = True,
) -> dict[str, Any]:
    dossier = build_evidence_dossier(claim, evidence_items, project=project, country=country)
    if persist:
        return write_evidence_dossier(dossier)
    return {"ok": True, "dossier": dossier}
