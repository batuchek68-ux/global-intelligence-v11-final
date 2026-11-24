"""Multi-agent cross-examination for intelligence claims.

Three roles inspect the same claim: analyst (case for), risk_gate (case against),
auditor (evidence quality). LLM is optional; deterministic fallback keeps CI stable.
"""
from __future__ import annotations

import os
from typing import Any


def _llm(system: str, prompt: str) -> str:
    if os.getenv("OPS_USE_LLM", "0") != "1":
        return ""
    try:
        from backend.services.llm_service import chat
        return chat([{"role": "system", "content": system}, {"role": "user", "content": prompt}], max_tokens=300, temperature=0.3).strip()
    except Exception:
        return ""


def debate(claim: str, evidence: list[str] | None = None, risk: str = "medium") -> dict[str, Any]:
    evidence = evidence or []
    sources = list(evidence)
    analyst = _llm(
        "You are an intelligence analyst. Argue the strongest evidence-backed case FOR the claim. Do not invent facts.",
        f"Claim: {claim}\nEvidence: {sources}\nCase FOR:",
    ) or f"Claim '{claim}' is supported only to the degree that the attached evidence confirms it: {len(sources)} item(s)."
    risk_gate = _llm(
        "You are a risk gate. Challenge the claim, list what is unverified and what could go wrong. Do not invent facts.",
        f"Claim: {claim}\nEvidence: {sources}\nRisk level: {risk}\nCase AGAINST:",
    ) or f"Unverified: causality, source credibility, and timeline. Risk level is {risk}; human verification required before external use."
    auditor = _llm(
        "You are an evidence auditor. Rate evidence sufficiency and name missing proof.",
        f"Claim: {claim}\nEvidence: {sources}\nAudit:",
    ) or f"Evidence count={len(sources)}; authoritative government/primary sources={'present' if any('gov' in s.lower() or 'official' in s.lower() for s in sources) else 'missing'}."
    confidence = 45 + min(30, len(sources) * 6)
    if risk == "high":
        confidence = min(confidence, 55)
    consensus = bool(sources) and risk != "high"
    return {
        "ok": True,
        "claim": claim,
        "perspectives": {"analyst": analyst, "risk_gate": risk_gate, "auditor": auditor},
        "consensus": consensus,
        "confidence": confidence,
        "requires_human": risk in {"high", "medium"} or not sources,
        "evidence": sources,
    }
