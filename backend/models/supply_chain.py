"""v12 Supply Chain data models — logistics, quality, milestones."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ShipmentStatus(Enum):
    PREPARING = "preparing"
    IN_TRANSIT = "in_transit"
    AT_PORT = "at_port"
    CUSTOMS_CLEARANCE = "customs_clearance"
    DELIVERED = "delivered"
    DELAYED = "delayed"
    LOST = "lost"


class QualityStatus(Enum):
    PENDING = "pending"
    INSPECTING = "inspecting"
    PASSED = "passed"
    FAILED = "failed"
    CONDITIONAL_PASS = "conditional_pass"


class MilestoneStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    BLOCKED = "blocked"


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Shipment:
    id: str
    contract_id: str
    carrier: str = ""
    tracking_number: str = ""
    origin_port: str = ""
    destination_port: str = ""
    vessel_name: str = ""
    voyage_number: str = ""
    etd: datetime | None = None       # Estimated Time of Departure
    eta: datetime | None = None       # Estimated Time of Arrival
    ata: datetime | None = None       # Actual Time of Arrival
    containers: list[dict[str, Any]] = field(default_factory=list)
    documents: list[str] = field(default_factory=list)  # e.g. ["B/L", "Packing List", "CO"]
    status: ShipmentStatus = ShipmentStatus.PREPARING
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class QualityInspection:
    id: str
    shipment_id: str
    inspector: str = ""
    inspection_date: datetime | None = None
    inspection_type: str = ""          # e.g. "pre-shipment", "during-production", "pre-delivery"
    sample_size: int = 0
    total_quantity: int = 0
    defects_found: int = 0
    aql_level: str = ""               # Acceptable Quality Level
    findings: list[dict[str, Any]] = field(default_factory=list)
    photos: list[str] = field(default_factory=list)
    report_url: str = ""
    status: QualityStatus = QualityStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Milestone:
    id: str
    contract_id: str
    name: str
    description: str = ""
    planned_date: datetime | None = None
    actual_date: datetime | None = None
    dependencies: list[str] = field(default_factory=list)
    status: MilestoneStatus = MilestoneStatus.NOT_STARTED
    progress_pct: float = 0.0
    notes: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SupplyChainAlert:
    id: str
    contract_id: str
    alert_type: str = ""              # e.g. "delay", "quality", "document", "payment"
    severity: AlertSeverity = AlertSeverity.INFO
    message: str = ""
    suggested_action: str = ""
    resolved: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
