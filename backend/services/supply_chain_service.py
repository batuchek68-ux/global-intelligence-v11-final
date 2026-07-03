"""v12 Supply Chain Service.

Tracks shipments, quality inspections, delivery milestones,
and generates alerts for supply chain disruptions.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.models.supply_chain import (
    AlertSeverity,
    Milestone,
    MilestoneStatus,
    QualityInspection,
    QualityStatus,
    Shipment,
    ShipmentStatus,
    SupplyChainAlert,
)

logger = logging.getLogger(__name__)

STORAGE = Path("backend/memory/supply_chain")
STORAGE.mkdir(parents=True, exist_ok=True)


# ── Shipment Tracking ──────────────────────────────────────────────

def create_shipment(
    contract_id: str,
    carrier: str = "",
    origin_port: str = "",
    destination_port: str = "",
    etd: datetime | None = None,
    eta: datetime | None = None,
) -> Shipment:
    shipment = Shipment(
        id=f"shp_{uuid.uuid4().hex[:12]}",
        contract_id=contract_id,
        carrier=carrier,
        origin_port=origin_port,
        destination_port=destination_port,
        etd=etd,
        eta=eta,
        status=ShipmentStatus.PREPARING,
    )
    _save_shipment(shipment)
    return shipment


def update_shipment_status(
    shipment_id: str,
    status: ShipmentStatus,
    event: dict[str, Any] | None = None,
) -> Shipment | None:
    shipment = _load_shipment(shipment_id)
    if not shipment:
        return None

    shipment.status = status
    if event:
        event["timestamp"] = datetime.now(timezone.utc).isoformat()
        shipment.events.append(event)

    _save_shipment(shipment)
    logger.info("Shipment %s → %s", shipment_id, status.value)
    return shipment


def track_shipment(shipment_id: str) -> dict[str, Any] | None:
    shipment = _load_shipment(shipment_id)
    if not shipment:
        return None

    now = datetime.now(timezone.utc)
    status_text = shipment.status.value
    alerts: list[str] = []

    if shipment.eta and now > shipment.eta and shipment.status != ShipmentStatus.DELIVERED:
        status_text = "overdue"
        alerts.append(f"Shipment overdue! ETA was {shipment.eta.strftime('%Y-%m-%d')}")

    return {
        "shipment_id": shipment.id,
        "contract_id": shipment.contract_id,
        "status": status_text,
        "carrier": shipment.carrier,
        "origin": shipment.origin_port,
        "destination": shipment.destination_port,
        "etd": shipment.etd.isoformat() if shipment.etd else None,
        "eta": shipment.eta.isoformat() if shipment.eta else None,
        "events": shipment.events,
        "alerts": alerts,
        "documents": shipment.documents,
    }


# ── Quality Inspection ─────────────────────────────────────────────

def create_inspection(
    shipment_id: str,
    inspector: str = "",
    inspection_type: str = "pre-shipment",
    total_quantity: int = 0,
) -> QualityInspection:
    inspection = QualityInspection(
        id=f"qi_{uuid.uuid4().hex[:12]}",
        shipment_id=shipment_id,
        inspector=inspector,
        inspection_type=inspection_type,
        total_quantity=total_quantity,
        status=QualityStatus.PENDING,
    )
    _save_inspection(inspection)
    return inspection


def record_inspection_result(
    inspection_id: str,
    status: QualityStatus,
    sample_size: int = 0,
    defects_found: int = 0,
    findings: list[dict[str, Any]] | None = None,
) -> QualityInspection | None:
    inspection = _load_inspection(inspection_id)
    if not inspection:
        return None

    inspection.status = status
    inspection.sample_size = sample_size
    inspection.defects_found = defects_found
    inspection.inspection_date = datetime.now(timezone.utc)
    if findings:
        inspection.findings = findings

    _save_inspection(inspection)
    return inspection


# ── Milestone Management ───────────────────────────────────────────

def create_milestone(
    contract_id: str,
    name: str,
    planned_date: datetime | None = None,
    description: str = "",
    dependencies: list[str] | None = None,
) -> Milestone:
    milestone = Milestone(
        id=f"ms_{uuid.uuid4().hex[:12]}",
        contract_id=contract_id,
        name=name,
        description=description,
        planned_date=planned_date,
        dependencies=dependencies or [],
    )
    _save_milestone(milestone)
    return milestone


def update_milestone(
    milestone_id: str,
    status: MilestoneStatus | None = None,
    progress_pct: float | None = None,
    actual_date: datetime | None = None,
) -> Milestone | None:
    milestone = _load_milestone(milestone_id)
    if not milestone:
        return None

    if status:
        milestone.status = status
    if progress_pct is not None:
        milestone.progress_pct = max(0.0, min(100.0, progress_pct))
    if actual_date:
        milestone.actual_date = actual_date

    _save_milestone(milestone)
    return milestone


def get_milestone_progress(contract_id: str) -> dict[str, Any]:
    milestones = _load_milestones_by_contract(contract_id)
    if not milestones:
        return {"contract_id": contract_id, "milestones": [], "overall_progress": 0.0}

    completed = sum(1 for m in milestones if m.status == MilestoneStatus.COMPLETED)
    delayed = sum(1 for m in milestones if m.status == MilestoneStatus.DELAYED)
    blocked = sum(1 for m in milestones if m.status == MilestoneStatus.BLOCKED)

    return {
        "contract_id": contract_id,
        "total": len(milestones),
        "completed": completed,
        "delayed": delayed,
        "blocked": blocked,
        "overall_progress": round(completed / max(len(milestones), 1) * 100, 1),
        "milestones": [
            {
                "id": m.id,
                "name": m.name,
                "status": m.status.value,
                "progress": m.progress_pct,
                "planned": m.planned_date.isoformat() if m.planned_date else None,
            }
            for m in milestones
        ],
    }


# ── Alert System ───────────────────────────────────────────────────

def generate_alert(
    contract_id: str,
    alert_type: str,
    severity: AlertSeverity,
    message: str,
    suggested_action: str = "",
) -> SupplyChainAlert:
    alert = SupplyChainAlert(
        id=f"al_{uuid.uuid4().hex[:12]}",
        contract_id=contract_id,
        alert_type=alert_type,
        severity=severity,
        message=message,
        suggested_action=suggested_action,
    )
    _save_alert(alert)
    logger.warning("Supply chain alert: [%s] %s", severity.value, message)
    return alert


def check_for_alerts(contract_id: str) -> list[SupplyChainAlert]:
    """Active monitoring: check shipments and milestones for issues."""
    alerts: list[SupplyChainAlert] = []

    shipments = _load_shipments_by_contract(contract_id)
    now = datetime.now(timezone.utc)
    for s in shipments:
        if s.eta and now > s.eta and s.status != ShipmentStatus.DELIVERED:
            alerts.append(generate_alert(
                contract_id,
                "delay",
                AlertSeverity.CRITICAL,
                f"Shipment {s.id} overdue since {s.eta.strftime('%Y-%m-%d')}",
                "Contact carrier immediately and notify buyer.",
            ))

    milestones = _load_milestones_by_contract(contract_id)
    for m in milestones:
        if m.planned_date and now > m.planned_date and m.status == MilestoneStatus.NOT_STARTED:
            alerts.append(generate_alert(
                contract_id,
                "milestone_missed",
                AlertSeverity.WARNING,
                f"Milestone '{m.name}' missed planned date {m.planned_date.strftime('%Y-%m-%d')}",
                "Review schedule and update stakeholders.",
            ))

    return alerts


# ── Persistence Helpers ────────────────────────────────────────────

def _save_shipment(shipment: Shipment) -> None:
    path = STORAGE / f"shipment_{shipment.id}.json"
    path.write_text(json.dumps({
        "id": shipment.id,
        "contract_id": shipment.contract_id,
        "carrier": shipment.carrier,
        "origin_port": shipment.origin_port,
        "destination_port": shipment.destination_port,
        "etd": shipment.etd.isoformat() if shipment.etd else None,
        "eta": shipment.eta.isoformat() if shipment.eta else None,
        "status": shipment.status.value,
        "events": shipment.events,
        "documents": shipment.documents,
        "created_at": shipment.created_at.isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_shipment(shipment_id: str) -> Shipment | None:
    path = STORAGE / f"shipment_{shipment_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Shipment(
        id=data["id"],
        contract_id=data["contract_id"],
        carrier=data.get("carrier", ""),
        origin_port=data.get("origin_port", ""),
        destination_port=data.get("destination_port", ""),
        etd=datetime.fromisoformat(data["etd"]) if data.get("etd") else None,
        eta=datetime.fromisoformat(data["eta"]) if data.get("eta") else None,
        status=ShipmentStatus(data.get("status", "preparing")),
        events=data.get("events", []),
        documents=data.get("documents", []),
    )


def _load_shipments_by_contract(contract_id: str) -> list[Shipment]:
    results: list[Shipment] = []
    for f in STORAGE.glob("shipment_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("contract_id") == contract_id:
                results.append(Shipment(
                    id=data["id"],
                    contract_id=data["contract_id"],
                    carrier=data.get("carrier", ""),
                    status=ShipmentStatus(data.get("status", "preparing")),
                    eta=datetime.fromisoformat(data["eta"]) if data.get("eta") else None,
                ))
        except Exception:
            continue
    return results


def _save_inspection(inspection: QualityInspection) -> None:
    path = STORAGE / f"inspection_{inspection.id}.json"
    path.write_text(json.dumps({
        "id": inspection.id,
        "shipment_id": inspection.shipment_id,
        "inspector": inspection.inspector,
        "inspection_type": inspection.inspection_type,
        "sample_size": inspection.sample_size,
        "total_quantity": inspection.total_quantity,
        "defects_found": inspection.defects_found,
        "status": inspection.status.value,
        "findings": inspection.findings,
        "created_at": inspection.created_at.isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_inspection(inspection_id: str) -> QualityInspection | None:
    path = STORAGE / f"inspection_{inspection_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return QualityInspection(
        id=data["id"],
        shipment_id=data["shipment_id"],
        inspector=data.get("inspector", ""),
        inspection_type=data.get("inspection_type", ""),
        sample_size=data.get("sample_size", 0),
        total_quantity=data.get("total_quantity", 0),
        defects_found=data.get("defects_found", 0),
        status=QualityStatus(data.get("status", "pending")),
        findings=data.get("findings", []),
    )


def _save_milestone(milestone: Milestone) -> None:
    path = STORAGE / f"milestone_{milestone.id}.json"
    path.write_text(json.dumps({
        "id": milestone.id,
        "contract_id": milestone.contract_id,
        "name": milestone.name,
        "description": milestone.description,
        "planned_date": milestone.planned_date.isoformat() if milestone.planned_date else None,
        "actual_date": milestone.actual_date.isoformat() if milestone.actual_date else None,
        "dependencies": milestone.dependencies,
        "status": milestone.status.value,
        "progress_pct": milestone.progress_pct,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_milestone(milestone_id: str) -> Milestone | None:
    path = STORAGE / f"milestone_{milestone_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return Milestone(
        id=data["id"],
        contract_id=data["contract_id"],
        name=data["name"],
        description=data.get("description", ""),
        planned_date=datetime.fromisoformat(data["planned_date"]) if data.get("planned_date") else None,
        actual_date=datetime.fromisoformat(data["actual_date"]) if data.get("actual_date") else None,
        dependencies=data.get("dependencies", []),
        status=MilestoneStatus(data.get("status", "not_started")),
        progress_pct=data.get("progress_pct", 0.0),
    )


def _load_milestones_by_contract(contract_id: str) -> list[Milestone]:
    results: list[Milestone] = []
    for f in STORAGE.glob("milestone_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("contract_id") == contract_id:
                results.append(Milestone(
                    id=data["id"],
                    contract_id=data["contract_id"],
                    name=data["name"],
                    description=data.get("description", ""),
                    planned_date=datetime.fromisoformat(data["planned_date"]) if data.get("planned_date") else None,
                    actual_date=datetime.fromisoformat(data["actual_date"]) if data.get("actual_date") else None,
                    dependencies=data.get("dependencies", []),
                    status=MilestoneStatus(data.get("status", "not_started")),
                    progress_pct=data.get("progress_pct", 0.0),
                ))
        except Exception:
            continue
    return results


def _save_alert(alert: SupplyChainAlert) -> None:
    path = STORAGE / f"alert_{alert.id}.json"
    path.write_text(json.dumps({
        "id": alert.id,
        "contract_id": alert.contract_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity.value,
        "message": alert.message,
        "suggested_action": alert.suggested_action,
        "resolved": alert.resolved,
        "created_at": alert.created_at.isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
