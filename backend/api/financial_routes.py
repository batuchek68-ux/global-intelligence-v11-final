"""v12 Financial Services API routes — payments, FX, credit, financing."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.services.financial_service import (
    assess_credit,
    create_payment,
    find_payment_routes,
    get_fx_position,
    recommend_financing,
    recommend_fx_hedge,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/finance", tags=["finance"])


@router.post("/payment/routes")
async def payment_routes(request: Request) -> dict[str, Any]:
    body = await request.json()
    from_country = body.get("from_country", "CN")
    to_country = body.get("to_country", "KZ")
    amount = body.get("amount", 10000)

    routes = find_payment_routes(from_country, to_country, amount)
    return {
        "from": from_country,
        "to": to_country,
        "amount": amount,
        "routes": [
            {"provider": r.provider, "fee_pct": r.fee_pct, "fixed_fee": r.fixed_fee, "days": r.estimated_days}
            for r in routes
        ],
    }


@router.post("/payment/create")
async def create_payment_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    return create_payment(
        contract_id=body["contract_id"],
        payer_id=body.get("payer_id", ""),
        payee_id=body.get("payee_id", ""),
        amount=body.get("amount", 0),
        currency=body.get("currency", "USD"),
        from_country=body.get("from_country", "CN"),
        to_country=body.get("to_country", "KZ"),
    )


@router.get("/fx/{base}/{quote}")
async def fx_position(base: str, quote: str) -> dict[str, Any]:
    pos = get_fx_position(base, quote)
    return {
        "pair": f"{base}/{quote}",
        "spot": pos.spot_rate,
        "volatility": pos.volatility,
        "trend": pos.trend,
        "timestamp": pos.last_updated.isoformat(),
    }


@router.post("/fx/hedge")
async def fx_hedge(request: Request) -> dict[str, Any]:
    body = await request.json()
    hedge = recommend_fx_hedge(
        contract_id=body["contract_id"],
        amount=body.get("amount", 0),
        exposure_currency=body.get("exposure_currency", "USD"),
        base_currency=body.get("base_currency", "CNY"),
    )
    return {
        "hedge_id": hedge.id,
        "action": hedge.recommended_action,
        "hedge_ratio": hedge.hedge_ratio,
        "estimated_savings": hedge.estimated_savings,
        "reasoning": hedge.reasoning,
    }


@router.post("/credit/assess")
async def credit_assess(request: Request) -> dict[str, Any]:
    body = await request.json()
    assessment = assess_credit(
        company_name=body["company_name"],
        country=body.get("country", ""),
        trade_history=body.get("trade_history", {}),
    )
    return {
        "company": assessment.company_name,
        "rating": assessment.rating.value,
        "score": assessment.score,
        "credit_limit": assessment.recommended_credit_limit,
        "payment_term": assessment.recommended_payment_term,
        "risk_factors": assessment.risk_factors,
    }


@router.post("/financing/recommend")
async def financing_recommend(request: Request) -> dict[str, Any]:
    body = await request.json()
    options = recommend_financing(
        contract_value=body.get("contract_value", 0),
        contract_currency=body.get("currency", "USD"),
        supplier_country=body.get("supplier_country", "CN"),
        buyer_country=body.get("buyer_country", "KZ"),
    )
    return {
        "contract_value": body.get("contract_value"),
        "options": [
            {
                "type": o.financing_type.value,
                "provider": o.provider,
                "amount": o.amount,
                "rate": o.interest_rate,
                "term_days": o.term_days,
                "score": o.score,
                "requirements": o.requirements,
            }
            for o in options
        ],
    }
