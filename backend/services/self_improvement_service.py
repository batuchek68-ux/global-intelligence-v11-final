from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.audit_service import append_audit


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SELF_IMPROVEMENT_DIR = BACKEND_ROOT / "memory" / "self_improvement"
SELF_IMPROVEMENT_STATE = SELF_IMPROVEMENT_DIR / "state.json"
SELF_IMPROVEMENT_REPORT_DIR = BACKEND_ROOT / "reports" / "self_improvement"

PROFESSIONAL_DOMAINS = {
    "international_trade": ["Incoterms", "customs", "payment risk", "supplier verification", "cross-border logistics"],
    "engineering_projects": ["EPC", "FIDIC", "feasibility", "tender review", "construction progress"],
    "investment_promotion": ["project packaging", "government confirmation", "developer mapping", "ROI", "PPP"],
    "research_intelligence": ["source grading", "paper search", "library search", "citation discipline", "evidence chain"],
    "political_risk": ["policy change", "sanctions", "elections", "regulatory shift", "public sentiment"],
    "video_media": ["country style", "short video script", "platform trend", "proof visuals", "caption pacing"],
    "social_communication": ["intent detection", "tone control", "stakeholder mapping", "risk escalation", "draft review"],
    "software_operations": ["tests", "cloud acceptance", "watchdog", "license gates", "audit log"],
}

AUTONOMOUS_REPAIR_BOUNDARY = {
    "allowed": [
        "syntax fixes",
        "test path fixes",
        "missing directory creation",
        "documentation consistency",
        "low-risk configuration validation",
        "search keyword expansion",
        "internal report generation",
    ],
    "blocked_without_human": [
        "external social posting",
        "customer commitments",
        "price quotations",
        "contract terms",
        "payments",
        "legal or sanctions conclusions",
        "deleting or rewriting audit evidence",
    ],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path() -> Path:
    override = os.getenv("V11_SELF_IMPROVEMENT_STATE")
    return Path(override) if override else SELF_IMPROVEMENT_STATE


def _report_dir() -> Path:
    override = os.getenv("V11_SELF_IMPROVEMENT_REPORT_DIR")
    return Path(override) if override else SELF_IMPROVEMENT_REPORT_DIR


def read_self_improvement_state(path: Path | None = None) -> dict[str, Any]:
    target = path or _state_path()
    if not target.exists():
        return {
            "ok": True,
            "path": str(target),
            "state": {
                "created_at": None,
                "updated_at": None,
                "cycles": [],
                "domain_scores": {},
            },
        }
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = {"created_at": None, "updated_at": None, "cycles": [], "domain_scores": {}}
    return {"ok": True, "path": str(target), "state": data}


def build_domain_assessment(evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    evidence = evidence or {}
    tests_passed = int(evidence.get("tests_passed", 0) or 0)
    tests_total = int(evidence.get("tests_total", tests_passed) or tests_passed or 1)
    cloud_ok = bool(evidence.get("cloud_acceptance_ok", False))
    integrity_ok = bool(evidence.get("system_integrity_ok", False))
    search_ok = bool(evidence.get("search_system_ok", False))
    social_gate_ok = bool(evidence.get("social_gate_ok", True))

    base = 62
    if tests_total:
        base += min(18, round((tests_passed / tests_total) * 18))
    if cloud_ok:
        base += 5
    if integrity_ok:
        base += 5
    if search_ok:
        base += 5
    if social_gate_ok:
        base += 5

    domain_scores = {}
    for domain, skills in PROFESSIONAL_DOMAINS.items():
        score = min(96, base)
        if domain == "social_communication" and not social_gate_ok:
            score = min(score, 68)
        if domain == "software_operations" and not (cloud_ok and integrity_ok):
            score = min(score, 78)
        domain_scores[domain] = {
            "score": score,
            "target": 95,
            "status": "strong" if score >= 88 else "improving",
            "skills": skills,
            "next_training": [
                "collect stronger evidence",
                "compare against domain expert checklist",
                "write lessons after every failure",
                "add regression tests for repeated mistakes",
            ],
        }
    return {
        "created_at": _now_iso(),
        "overall_score": round(sum(item["score"] for item in domain_scores.values()) / len(domain_scores)),
        "domain_scores": domain_scores,
        "boundary": AUTONOMOUS_REPAIR_BOUNDARY,
        "human_level_goal": "Approach expert human judgment through evidence, tests, review loops, and risk gates; never bypass approval.",
    }


def build_self_improvement_plan(evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    assessment = build_domain_assessment(evidence)
    gaps = []
    for domain, data in assessment["domain_scores"].items():
        if data["score"] < data["target"]:
            gaps.append(
                {
                    "domain": domain,
                    "score": data["score"],
                    "target": data["target"],
                    "actions": [
                        "expand authoritative search terms",
                        "add domain-specific source grading",
                        "produce internal brief and compare with outcome",
                        "convert repeated mistakes into tests",
                    ],
                }
            )
    plan = {
        "ok": True,
        "created_at": _now_iso(),
        "assessment": assessment,
        "gaps": gaps,
        "daily_loop": [
            "collect evidence from search, projects, forums, social, videos, and official sources",
            "score value, growth, political impact, attention, and project relevance",
            "generate internal brief and video-learning notes",
            "run system integrity, tests, autonomous repair, and cloud acceptance",
            "append lessons and audit records",
        ],
        "repair_policy": AUTONOMOUS_REPAIR_BOUNDARY,
    }
    return plan


def run_self_improvement_cycle(evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    state_result = read_self_improvement_state()
    state = state_result["state"]
    if not state.get("created_at"):
        state["created_at"] = _now_iso()

    plan = build_self_improvement_plan(evidence)
    cycle = {
        "created_at": _now_iso(),
        "overall_score": plan["assessment"]["overall_score"],
        "gaps": plan["gaps"],
        "repair_policy": AUTONOMOUS_REPAIR_BOUNDARY,
    }
    cycles = list(state.get("cycles") or [])
    cycles.append(cycle)
    state["cycles"] = cycles[-120:]
    state["updated_at"] = _now_iso()
    state["domain_scores"] = plan["assessment"]["domain_scores"]

    target = _state_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    report_dir = _report_dir()
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "latest.md"
    lines = [
        "# v11 Self Improvement Report",
        "",
        "DRAFT - internal operations record",
        "",
        f"- Generated: {cycle['created_at']}",
        f"- Overall score: {cycle['overall_score']}",
        "",
        "## Domain Scores",
        "",
    ]
    for domain, data in state["domain_scores"].items():
        lines.append(f"- {domain}: {data['score']} / target {data['target']} ({data['status']})")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Low-risk technical repair can be autonomous.",
            "- External communication, commitments, payments, contracts, legal/sanctions conclusions, and audit deletion require human approval.",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    append_audit(
        "SELF_IMPROVEMENT_CYCLE",
        "DONE",
        f"Completed self-improvement cycle overall_score={cycle['overall_score']}; high-risk actions remain approval-gated.",
        confidence=92,
        risk="LOW",
    )
    return {"ok": True, "state_path": str(target), "report_path": str(report_path), "plan": plan, "cycle": cycle}
