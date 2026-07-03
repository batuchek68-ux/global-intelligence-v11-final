"""v12 Matching Engine data models — buyer-supplier matching, quotes, contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class MatchStatus(Enum):
    PENDING = "pending"
    REVIEWING = "reviewing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class QuoteStatus(Enum):
    DRAFT = "draft"
    SENT = "sent"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ContractStatus(Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    PENDING_SIGNATURE = "pending_signature"
    SIGNED = "signed"
    TERMINATED = "terminated"
    EXPIRED = "expired"


class PaymentTerm(Enum):
    T_T = "T/T"                      # Telegraphic Transfer
    L_C = "L/C"                      # Letter of Credit
    D_P = "D/P"                      # Documents against Payment
    D_A = "D/A"                      # Documents against Acceptance
    OA = "O/A"                       # Open Account
    ADVANCE = "advance"              # 100% advance
    CUSTOM = "custom"


class Incoterm(Enum):
    FOB = "FOB"
    CIF = "CIF"
    EXW = "EXW"
    CFR = "CFR"
    DDP = "DDP"
    DAP = "DAP"


@dataclass
class BuyerRequirement:
    id: str
    buyer_id: str
    title: str
    product_category: str
    hs_code: str = ""
    specifications: dict[str, Any] = field(default_factory=dict)
    quantity: dict[str, Any] = field(default_factory=dict)  # e.g. {"min": 100, "max": 500, "unit": "pcs"}
    target_price: dict[str, Any] = field(default_factory=dict)  # e.g. {"currency": "USD", "min": 10, "max": 15}
    preferred_incoterm: Incoterm = Incoterm.FOB
    preferred_payment: PaymentTerm = PaymentTerm.T_T
    delivery_port: str = ""
    target_countries: list[str] = field(default_factory=list)
    certifications_required: list[str] = field(default_factory=list)
    timeline: dict[str, str] = field(default_factory=dict)  # e.g. {"delivery": "2026-09-01"}
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SupplierProfile:
    id: str
    supplier_id: str
    company_name: str
    country: str
    product_categories: list[str] = field(default_factory=list)
    hs_codes: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    annual_capacity: dict[str, Any] = field(default_factory=dict)
    min_order_quantity: dict[str, Any] = field(default_factory=dict)
    export_history: list[str] = field(default_factory=list)
    quality_rating: float = 0.0  # 0-5
    response_time_hours: float = 0.0
    verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MatchResult:
    id: str
    requirement_id: str
    supplier_id: str
    score: float                  # 0-100 composite score
    price_match: float            # 0-100
    quality_match: float          # 0-100
    certification_match: float    # 0-100
    capacity_match: float         # 0-100
    logistics_match: float        # 0-100
    status: MatchStatus = MatchStatus.PENDING
    explanation: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class QuoteRequest:
    id: str
    requirement_id: str
    supplier_ids: list[str] = field(default_factory=list)
    quantity: dict[str, Any] = field(default_factory=dict)
    incoterm: Incoterm = Incoterm.FOB
    port: str = ""
    deadline: datetime | None = None
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Quote:
    id: str
    quote_request_id: str
    supplier_id: str
    price_per_unit: float
    currency: str = "USD"
    total_amount: float = 0.0
    incoterm: Incoterm = Incoterm.FOB
    payment_term: PaymentTerm = PaymentTerm.T_T
    delivery_days: int = 30
    valid_until: datetime | None = None
    status: QuoteStatus = QuoteStatus.DRAFT
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Contract:
    id: str
    quote_id: str
    buyer_id: str
    supplier_id: str
    product_description: str
    quantity: dict[str, Any] = field(default_factory=dict)
    unit_price: float = 0.0
    currency: str = "USD"
    total_value: float = 0.0
    incoterm: Incoterm = Incoterm.FOB
    payment_term: PaymentTerm = PaymentTerm.T_T
    delivery_schedule: dict[str, Any] = field(default_factory=dict)
    quality_standards: dict[str, Any] = field(default_factory=dict)
    penalty_clauses: dict[str, Any] = field(default_factory=dict)
    force_majeure: str = ""
    governing_law: str = ""
    status: ContractStatus = ContractStatus.DRAFT
    risk_flags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
