from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class User:
    id: str
    org_id: str
    role: str = "operator"
    active: bool = True


@dataclass
class Tenant:
    id: str
    name: str
    status: str = "active"


@dataclass
class ProjectIntake:
    title: str
    country: str = "Unknown"
    counterparty: str = "Unknown"
    amount_usd: float = 0.0
    stage: str = "intake"
    latest_communication: str = ""
    risks: list[str] = field(default_factory=list)
    next_decision: str = ""


@dataclass
class ApprovalDecision:
    project: str
    decision: str
    source: str = "api"
    note: str = ""
    created_at: str = field(default_factory=now_iso)


@dataclass
class ServiceResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
