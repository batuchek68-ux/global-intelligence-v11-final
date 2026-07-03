"""v12 Financial Services data models — payments, FX, credit, financing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class PaymentStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class FXDirection(Enum):
    BUY = "buy"
    SELL = "sell"


class CreditRating(Enum):
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    C = "C"
    D = "D"
    UNRATED = "unrated"


class FinancingType(Enum):
    FACTORING = "factoring"            # 保理
    LETTER_OF_CREDIT = "letter_of_credit"
    SUPPLY_CHAIN = "supply_chain"      # 供应链金融
    EXPORT_CREDIT = "export_credit"    # 出口信贷
    INVENTORY = "inventory"            # 库存融资


@dataclass
class PaymentRoute:
    """Optimal payment routing between two countries."""
    from_country: str
    to_country: str
    from_currency: str
    to_currency: str
    provider: str = ""                 # e.g. "SWIFT", "Wise", "Payoneer"
    fee_pct: float = 0.0
    fixed_fee: float = 0.0
    estimated_days: int = 3
    exchange_rate_markup: float = 0.0  # percentage
    min_amount: float = 0.0
    max_amount: float = 0.0


@dataclass
class Payment:
    id: str
    contract_id: str
    payer_id: str
    payee_id: str
    amount: float
    currency: str = "USD"
    provider: str = "SWIFT"
    route: PaymentRoute | None = None
    reference: str = ""
    status: PaymentStatus = PaymentStatus.PENDING
    fx_rate: float | None = None
    fees: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class FXPosition:
    """Foreign exchange position for a given currency pair."""
    base_currency: str
    quote_currency: str
    spot_rate: float
    forward_1m: float | None = None
    forward_3m: float | None = None
    forward_6m: float | None = None
    volatility: float = 0.0          # annualized volatility
    trend: str = "stable"            # "appreciating", "depreciating", "stable"
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class FXHedge:
    """FX hedging recommendation."""
    id: str
    contract_id: str
    exposure_amount: float
    exposure_currency: str
    base_currency: str
    recommended_action: str = ""       # e.g. "forward_contract", "option", "natural_hedge"
    hedge_ratio: float = 1.0          # 0.0 (no hedge) to 1.0 (full hedge)
    estimated_savings: float = 0.0
    reasoning: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CreditAssessment:
    id: str
    company_id: str
    company_name: str
    country: str
    rating: CreditRating = CreditRating.UNRATED
    score: float = 0.0               # 0-100
    payment_history: dict[str, Any] = field(default_factory=dict)
    financial_health: dict[str, Any] = field(default_factory=dict)
    trade_references: list[dict[str, Any]] = field(default_factory=list)
    recommended_credit_limit: float = 0.0
    recommended_payment_term: str = ""
    risk_factors: list[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class FinancingOption:
    id: str
    contract_id: str
    financing_type: FinancingType
    amount: float
    currency: str = "USD"
    provider: str = ""
    interest_rate: float = 0.0
    term_days: int = 90
    fees: float = 0.0
    requirements: list[str] = field(default_factory=list)
    estimated_approval_days: int = 7
    score: float = 0.0               # suitability score 0-100
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
