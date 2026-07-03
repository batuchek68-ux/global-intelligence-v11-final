"""v12 Financial Services.

Cross-border payments, FX risk management, credit assessment,
and trade financing recommendations.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.models.finance import (
    CreditAssessment,
    CreditRating,
    FinancingOption,
    FinancingType,
    FXHedge,
    FXPosition,
    Payment,
    PaymentRoute,
    PaymentStatus,
)

logger = logging.getLogger(__name__)

STORAGE = Path("backend/memory/finance")
STORAGE.mkdir(parents=True, exist_ok=True)


# ── Payment Routing ────────────────────────────────────────────────

# Pre-configured payment corridors (extensible via plugins)
PAYMENT_CORRIDORS: list[PaymentRoute] = [
    PaymentRoute("CN", "KZ", "CNY", "KZT", "SWIFT", 0.1, 25.0, 3, 0.5),
    PaymentRoute("CN", "US", "CNY", "USD", "Wise", 0.5, 5.0, 1, 0.3, 1, 500000),
    PaymentRoute("CN", "EU", "CNY", "EUR", "SWIFT", 0.1, 30.0, 2, 0.4),
    PaymentRoute("KZ", "CN", "KZT", "CNY", "SWIFT", 0.15, 20.0, 3, 0.6),
    PaymentRoute("US", "CN", "USD", "CNY", "Payoneer", 1.0, 15.0, 2, 0.5, 100, 100000),
]


def find_payment_routes(from_country: str, to_country: str, amount: float) -> list[PaymentRoute]:
    """Find available payment routes between two countries."""
    routes = [
        r for r in PAYMENT_CORRIDORS
        if r.from_country == from_country and r.to_country == to_country
        and (r.min_amount == 0 or amount >= r.min_amount)
        and (r.max_amount == 0 or amount <= r.max_amount)
    ]

    if not routes:
        return [PaymentRoute(
            from_country, to_country,
            from_currency="USD", to_currency="USD",
            provider="SWIFT", fee_pct=0.2, fixed_fee=35.0,
            estimated_days=5,
        )]

    return sorted(routes, key=lambda r: r.fixed_fee + amount * r.fee_pct / 100)


def create_payment(
    contract_id: str,
    payer_id: str,
    payee_id: str,
    amount: float,
    currency: str = "USD",
    from_country: str = "CN",
    to_country: str = "KZ",
) -> dict[str, Any]:
    """Create a payment with optimal routing."""
    routes = find_payment_routes(from_country, to_country, amount)
    best_route = routes[0] if routes else None

    payment = Payment(
        id=f"pay_{uuid.uuid4().hex[:12]}",
        contract_id=contract_id,
        payer_id=payer_id,
        payee_id=payee_id,
        amount=amount,
        currency=currency,
        provider=best_route.provider if best_route else "SWIFT",
        route=best_route,
        status=PaymentStatus.PENDING,
        fees=best_route.fixed_fee + amount * best_route.fee_pct / 100 if best_route else 0,
    )

    _persist_payment(payment)

    return {
        "payment_id": payment.id,
        "amount": amount,
        "currency": currency,
        "provider": payment.provider,
        "estimated_fees": round(payment.fees, 2),
        "estimated_days": best_route.estimated_days if best_route else 5,
        "status": payment.status.value,
        "alternative_routes": [
            {"provider": r.provider, "fees": round(r.fixed_fee + amount * r.fee_pct / 100, 2), "days": r.estimated_days}
            for r in routes[1:4]
        ],
    }


# ── FX Risk Management ─────────────────────────────────────────────

def get_fx_position(base: str, quote: str) -> FXPosition:
    """Get current FX position for a currency pair."""
    fx_map: dict[str, dict[str, Any]] = {
        ("USD", "CNY"): {"spot": 7.25, "vol": 0.06, "trend": "appreciating"},
        ("CNY", "USD"): {"spot": 0.138, "vol": 0.06, "trend": "depreciating"},
        ("USD", "KZT"): {"spot": 460.0, "vol": 0.10, "trend": "depreciating"},
        ("EUR", "USD"): {"spot": 1.08, "vol": 0.05, "trend": "stable"},
        ("CNY", "KZT"): {"spot": 63.5, "vol": 0.08, "trend": "stable"},
    }

    info = fx_map.get((base, quote), {"spot": 1.0, "vol": 0.05, "trend": "stable"})
    return FXPosition(
        base_currency=base,
        quote_currency=quote,
        spot_rate=info["spot"],
        volatility=info["vol"],
        trend=info["trend"],
    )


def recommend_fx_hedge(
    contract_id: str,
    amount: float,
    exposure_currency: str,
    base_currency: str = "CNY",
) -> FXHedge:
    """Recommend FX hedging strategy."""
    pos = get_fx_position(exposure_currency, base_currency)

    if pos.volatility < 0.03:
        action = "natural_hedge"
        hedge_ratio = 0.0
        reasoning = "Low volatility pair, natural hedging sufficient."
    elif pos.volatility < 0.08:
        action = "forward_contract"
        hedge_ratio = 0.5
        reasoning = f"Moderate volatility ({pos.volatility:.0%}), 50% forward hedge recommended."
    else:
        action = "forward_contract_or_option"
        hedge_ratio = 0.8
        reasoning = f"High volatility ({pos.volatility:.0%}), 80% hedge via forwards or options."

    potential_loss = amount * pos.volatility * 0.5  # rough VaR
    estimated_savings = potential_loss * hedge_ratio

    return FXHedge(
        id=f"fh_{uuid.uuid4().hex[:12]}",
        contract_id=contract_id,
        exposure_amount=amount,
        exposure_currency=exposure_currency,
        base_currency=base_currency,
        recommended_action=action,
        hedge_ratio=hedge_ratio,
        estimated_savings=round(estimated_savings, 2),
        reasoning=reasoning,
    )


# ── Credit Assessment ──────────────────────────────────────────────

def assess_credit(
    company_name: str,
    country: str,
    trade_history: dict[str, Any] | None = None,
) -> CreditAssessment:
    """Assess creditworthiness of a trading partner."""
    trade_history = trade_history or {}

    volume = trade_history.get("total_volume", 0)
    on_time_rate = trade_history.get("on_time_delivery_rate", 0.95)
    dispute_count = trade_history.get("dispute_count", 0)
    years_active = trade_history.get("years_active", 3)

    # Scoring model
    volume_score = min(volume / 1_000_000 * 30, 30)
    delivery_score = on_time_rate * 25
    dispute_score = max(15 - dispute_count * 5, 0)
    age_score = min(years_active * 3, 15)
    total_score = volume_score + delivery_score + dispute_score + age_score

    if total_score >= 85:
        rating = CreditRating.A
        limit_factor = 0.30
    elif total_score >= 70:
        rating = CreditRating.BBB
        limit_factor = 0.20
    elif total_score >= 55:
        rating = CreditRating.BB
        limit_factor = 0.10
    elif total_score >= 40:
        rating = CreditRating.B
        limit_factor = 0.05
    else:
        rating = CreditRating.C
        limit_factor = 0.02

    return CreditAssessment(
        id=f"ca_{uuid.uuid4().hex[:12]}",
        company_id=company_name.lower().replace(" ", "_"),
        company_name=company_name,
        country=country,
        rating=rating,
        score=round(total_score, 1),
        payment_history={"on_time_rate": on_time_rate, "disputes": dispute_count},
        financial_health={"years_active": years_active, "total_volume": volume},
        recommended_credit_limit=round(volume * limit_factor, 2),
        recommended_payment_term="T/T 30% advance + 70% before shipment" if rating.value >= "BBB" else "100% advance or L/C",
        risk_factors=_identify_risk_factors(rating, country, dispute_count),
    )


def _identify_risk_factors(rating: CreditRating, country: str, disputes: int) -> list[str]:
    risks: list[str] = []
    if rating.value <= "BB":
        risks.append(f"Below investment-grade credit rating ({rating.value})")
    if disputes > 2:
        risks.append(f"High dispute count ({disputes})")
    high_risk_countries = {"VE", "IR", "KP", "SY", "CU", "SD"}
    if country in high_risk_countries:
        risks.append(f"High-risk jurisdiction ({country})")
    return risks


# ── Trade Financing ────────────────────────────────────────────────

def recommend_financing(
    contract_value: float,
    contract_currency: str = "USD",
    supplier_country: str = "CN",
    buyer_country: str = "KZ",
) -> list[FinancingOption]:
    """Recommend trade financing options."""
    options: list[FinancingOption] = []

    # Factoring (保理)
    if contract_value >= 10_000:
        options.append(FinancingOption(
            id=f"fn_{uuid.uuid4().hex[:12]}",
            contract_id="",
            financing_type=FinancingType.FACTORING,
            amount=contract_value * 0.85,
            currency=contract_currency,
            provider="Standard Chartered",
            interest_rate=6.5,
            term_days=90,
            fees=contract_value * 0.02,
            requirements=["Invoice", "Bill of Lading", "Packing List"],
            estimated_approval_days=5,
            score=85,
        ))

    # Letter of Credit
    options.append(FinancingOption(
        id=f"fn_{uuid.uuid4().hex[:12]}",
        contract_id="",
        financing_type=FinancingType.LETTER_OF_CREDIT,
        amount=contract_value,
        currency=contract_currency,
        provider="ICBC",
        interest_rate=3.5,
        term_days=180,
        fees=contract_value * 0.01,
        requirements=["Purchase Contract", "Proforma Invoice"],
        estimated_approval_days=10,
        score=75,
    ))

    # Supply Chain Finance
    if contract_value >= 50_000:
        options.append(FinancingOption(
            id=f"fn_{uuid.uuid4().hex[:12]}",
            contract_id="",
            financing_type=FinancingType.SUPPLY_CHAIN,
            amount=contract_value * 0.70,
            currency=contract_currency,
            provider="HSBC",
            interest_rate=5.0,
            term_days=120,
            fees=contract_value * 0.015,
            requirements=["Supply Chain Agreement", "3-Year Trading History"],
            estimated_approval_days=15,
            score=65,
        ))

    return sorted(options, key=lambda o: o.score, reverse=True)


# ── Persistence ────────────────────────────────────────────────────

def _persist_payment(payment: Payment) -> None:
    (STORAGE / f"payment_{payment.id}.json").write_text(json.dumps({
        "id": payment.id,
        "contract_id": payment.contract_id,
        "payer_id": payment.payer_id,
        "payee_id": payment.payee_id,
        "amount": payment.amount,
        "currency": payment.currency,
        "provider": payment.provider,
        "status": payment.status.value,
        "fees": payment.fees,
        "created_at": payment.created_at.isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
