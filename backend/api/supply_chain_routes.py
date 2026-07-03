"""v12 Supply Chain API routes — shipments, quality, milestones, alerts."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.models.supply_chain import (
    AlertSeverity,
    MilestoneStatus,
    QualityStatus,
    ShipmentStatus,
)
from backend.services.supply_chain_service import (
    check_for_alerts,
    create_inspection,
    create_milestone,
    create_shipment,
    generate_alert,
    get_milestone_progress,
    record_inspection_result,
    track_shipment,
    update_milestone,
    update_shipment_status,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/supply-chain", tags=["supply-chain"])


@router.post("/shipments")
async def create_shipment_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    etd = datetime.fromisoformat(body["etd"]) if body.get("etd") else None
    eta = datetime.fromisoformat(body["eta"]) if body.get("eta") else None

    shipment = create_shipment(
        contract_id=body["contract_id"],
        carrier=body.get("carrier", ""),
        origin_port=body.get("origin_port", ""),
        destination_port=body.get("destination_port", ""),
        etd=etd,
        eta=eta,
    )
    return {
        "shipment_id": shipment.id,
        "status": shipment.status.value,
        "contract_id": shipment.contract_id,
    }


@router.get("/shipments/{shipment_id}")
async def get_shipment(shipment_id: str) -> dict[str, Any]:
    result = track_shipment(shipment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return result


@router.post("/shipments/{shipment_id}/status")
async def update_shipment_status_endpoint(shipment_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    status = ShipmentStatus(body["status"])
    event = body.get("event", {})

    shipment = update_shipment_status(shipment_id, status, event)
    if shipment is None:
        raise HTTPException(status_code=404, detail="Shipment not found")
    return {"shipment_id": shipment.id, "status": shipment.status.value}


@router.post("/quality/inspections")
async def create_inspection_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    inspection = create_inspection(
        shipment_id=body["shipment_id"],
        inspector=body.get("inspector", ""),
        inspection_type=body.get("inspection_type", "pre-shipment"),
        total_quantity=body.get("total_quantity", 0),
    )
    return {"inspection_id": inspection.id, "status": inspection.status.value}


@router.post("/quality/inspections/{inspection_id}/result")
async def record_inspection_result_endpoint(inspection_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    status = QualityStatus(body["status"])

    result = record_inspection_result(
        inspection_id,
        status,
        body.get("sample_size", 0),
        body.get("defects_found", 0),
        body.get("findings", []),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return {"inspection_id": result.id, "status": result.status.value}


@router.post("/milestones")
async def create_milestone_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    planned = datetime.fromisoformat(body["planned_date"]) if body.get("planned_date") else None

    milestone = create_milestone(
        contract_id=body["contract_id"],
        name=body["name"],
        planned_date=planned,
        description=body.get("description", ""),
        dependencies=body.get("dependencies", []),
    )
    return {"milestone_id": milestone.id, "name": milestone.name, "status": milestone.status.value}


@router.post("/milestones/{milestone_id}")
async def update_milestone_endpoint(milestone_id: str, request: Request) -> dict[str, Any]:
    body = await request.json()
    status = MilestoneStatus(body["status"]) if body.get("status") else None
    actual = datetime.fromisoformat(body["actual_date"]) if body.get("actual_date") else None

    result = update_milestone(milestone_id, status, body.get("progress_pct"), actual)
    if result is None:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return {"milestone_id": result.id, "status": result.status.value, "progress_pct": result.progress_pct}


@router.get("/contracts/{contract_id}/progress")
async def get_contract_progress(contract_id: str) -> dict[str, Any]:
    return get_milestone_progress(contract_id)


@router.get("/contracts/{contract_id}/alerts")
async def get_contract_alerts(contract_id: str) -> dict[str, Any]:
    alerts = check_for_alerts(contract_id)
    return {
        "contract_id": contract_id,
        "alert_count": len(alerts),
        "alerts": [
            {"id": a.id, "type": a.alert_type, "severity": a.severity.value, "message": a.message, "action": a.suggested_action}
            for a in alerts
        ],
    }
