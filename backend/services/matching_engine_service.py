"""v12 Matching Engine Service.

Intelligent buyer-supplier matching with multi-dimensional scoring:
price, quality, certifications, capacity, logistics.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.models.matching import (
    BuyerRequirement,
    Contract,
    ContractStatus,
    Incoterm,
    MatchResult,
    MatchStatus,
    PaymentTerm,
    Quote,
    QuoteRequest,
    QuoteStatus,
    SupplierProfile,
)

logger = logging.getLogger(__name__)

STORAGE = Path("backend/memory/matching")
STORAGE.mkdir(parents=True, exist_ok=True)


# ── Scoring Engine ─────────────────────────────────────────────────

def _score_dimension(
    req_val: Any, sup_val: Any, weight: float = 1.0
) -> float:
    """Score a single matching dimension."""
    if req_val is None or sup_val is None:
        return 50.0 * weight

    if isinstance(req_val, (int, float)) and isinstance(sup_val, (int, float)):
        if req_val == 0:
            return 100.0 * weight if sup_val == 0 else 50.0 * weight
        ratio = min(req_val, sup_val) / max(req_val, sup_val)
        return ratio * 100.0 * weight

    if isinstance(req_val, list) and isinstance(sup_val, list):
        if not req_val:
            return 100.0 * weight
        overlap = len(set(req_val) & set(sup_val))
        return (overlap / len(req_val)) * 100.0 * weight

    return (100.0 if req_val == sup_val else 0.0) * weight


def match_supplier(
    requirement: BuyerRequirement,
    supplier: SupplierProfile,
) -> MatchResult:
    """Score a supplier against a buyer requirement."""
    price_score = _score_dimension(
        requirement.target_price.get("max"),
        requirement.target_price.get("max"),
        1.0,
    ) if requirement.target_price else 50.0

    quality_score = _score_dimension(
        requirement.certifications_required,
        supplier.certifications,
        1.0,
    )

    cert_score = _score_dimension(
        requirement.product_category,
        supplier.product_categories,
        1.0,
    )

    capacity_score = _score_dimension(
        requirement.quantity.get("max"),
        supplier.annual_capacity.get("max") if supplier.annual_capacity else None,
        0.8,
    )

    logistics_score = _score_dimension(
        requirement.target_countries,
        supplier.export_history,
        0.6,
    )

    composite = (
        price_score * 0.25
        + quality_score * 0.25
        + cert_score * 0.20
        + capacity_score * 0.15
        + logistics_score * 0.15
    )

    return MatchResult(
        id=f"match_{uuid.uuid4().hex[:12]}",
        requirement_id=requirement.id,
        supplier_id=supplier.supplier_id,
        score=round(composite, 2),
        price_match=round(price_score, 2),
        quality_match=round(quality_score, 2),
        certification_match=round(cert_score, 2),
        capacity_match=round(capacity_score, 2),
        logistics_match=round(logistics_score, 2),
        explanation=_build_explanation(composite, price_score, quality_score),
    )


def _build_explanation(composite: float, price: float, quality: float) -> str:
    if composite >= 80:
        return f"Strong match (score={composite:.0f}). Excellent price ({price:.0f}) and quality ({quality:.0f}) alignment."
    elif composite >= 60:
        return f"Good match (score={composite:.0f}). Consider on price={price:.0f}, quality={quality:.0f}."
    elif composite >= 40:
        return f"Fair match (score={composite:.0f}). Verify price and certifications."
    else:
        return f"Weak match (score={composite:.0f}). Significant gaps in alignment."


# ── Matching API ───────────────────────────────────────────────────

def search_matches(
    requirement: BuyerRequirement,
    suppliers: list[SupplierProfile],
    top_k: int = 10,
) -> list[MatchResult]:
    """Find best supplier matches for a buyer requirement."""
    results = [match_supplier(requirement, s) for s in suppliers]
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k]


def generate_quote(
    match_result: MatchResult,
    quantity: int = 100,
    price_per_unit: float = 0.0,
    currency: str = "USD",
    delivery_days: int = 30,
) -> Quote:
    """Generate a quote based on a match result."""
    return Quote(
        id=f"q_{uuid.uuid4().hex[:12]}",
        quote_request_id=f"qr_{match_result.requirement_id}",
        supplier_id=match_result.supplier_id,
        price_per_unit=price_per_unit,
        currency=currency,
        total_amount=price_per_unit * quantity,
        incoterm=Incoterm.FOB,
        payment_term=PaymentTerm.T_T,
        delivery_days=delivery_days,
        valid_until=datetime.now(timezone.utc),
        status=QuoteStatus.DRAFT,
    )


def generate_contract(quote: Quote, buyer_id: str, product_desc: str) -> Contract:
    """Generate a contract template from an accepted quote."""
    risk_flags: list[str] = []
    if quote.delivery_days > 60:
        risk_flags.append("Long delivery timeline (>60 days)")
    if quote.total_amount > 100_000:
        risk_flags.append(f"High-value contract (${quote.total_amount:,.0f})")

    return Contract(
        id=f"ctr_{uuid.uuid4().hex[:12]}",
        quote_id=quote.id,
        buyer_id=buyer_id,
        supplier_id=quote.supplier_id,
        product_description=product_desc,
        unit_price=quote.price_per_unit,
        currency=quote.currency,
        total_value=quote.total_amount,
        incoterm=quote.incoterm,
        payment_term=quote.payment_term,
        risk_flags=risk_flags,
    )


def compare_quotes(quotes: list[Quote]) -> dict[str, Any]:
    """Compare multiple quotes and recommend the best."""
    if not quotes:
        return {"error": "No quotes to compare"}

    sorted_quotes = sorted(quotes, key=lambda q: q.total_amount)
    best = sorted_quotes[0]

    return {
        "total_quotes": len(quotes),
        "best_quote": {
            "id": best.id,
            "supplier_id": best.supplier_id,
            "unit_price": best.price_per_unit,
            "currency": best.currency,
            "total": best.total_amount,
            "delivery_days": best.delivery_days,
        },
        "price_range": {
            "min": sorted_quotes[0].total_amount,
            "max": sorted_quotes[-1].total_amount,
            "avg": sum(q.total_amount for q in quotes) / len(quotes),
        },
        "all_quotes": [
            {"id": q.id, "supplier": q.supplier_id, "price": q.price_per_unit, "total": q.total_amount}
            for q in sorted_quotes
        ],
    }
