from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.integrations.event_bus import EventBus, EventTypes
from backend.integrations.n8n_connector import N8NConnector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])
event_bus = EventBus()


@router.post("/n8n/trigger/{workflow_id}")
async def trigger_n8n_workflow(
    workflow_id: str,
    org_id: str,
    user_id: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Trigger n8n only through the v11 approval gate."""
    try:
        payload = dict(data)
        payload.setdefault("org_id", org_id)
        payload.setdefault("user_id", user_id)
        result = N8NConnector().trigger_workflow(
            workflow_id=workflow_id,
            input_data=payload,
            org_id=org_id,
        )
        if result.get("status") == "blocked_by_v11_risk_gate":
            return {"status": "blocked_by_v11_risk_gate", "workflow_id": workflow_id, "result": result}
        if result.get("status") != "success":
            return {"status": "not_triggered", "workflow_id": workflow_id, "result": result}

        await event_bus.publish(
            EventTypes.WORKFLOW_TRIGGERED,
            {
                "workflow_id": workflow_id,
                "org_id": org_id,
                "user_id": user_id,
                "execution_id": result.get("workflow_execution_id"),
            },
        )
        return {
            "status": "success",
            "workflow_id": workflow_id,
            "execution_id": result.get("workflow_execution_id"),
        }
    except Exception as exc:
        logger.exception("Failed to trigger n8n workflow through v11 gate")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/n8n/workflows")
async def list_n8n_workflows(org_id: str) -> dict[str, Any]:
    """List n8n workflows when runtime n8n credentials are configured."""
    try:
        return {
            "status": "success",
            "org_id": org_id,
            "workflows": N8NConnector().list_workflows(),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/n8n/webhook")
async def n8n_webhook(request: Request) -> dict[str, Any]:
    """Receive n8n callbacks as internal events; never publish externally."""
    try:
        body = await request.json()
        await event_bus.publish(
            EventTypes.WORKFLOW_COMPLETED,
            {
                "workflow_execution_id": body.get("executionId"),
                "status": body.get("status"),
                "data": body.get("data"),
            },
        )
        return {"status": "received"}
    except Exception as exc:
        logger.exception("Failed to process n8n webhook")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sync-data")
async def sync_codex_n8n_data(org_id: str, sync_type: str = "insights") -> dict[str, Any]:
    """Record an internal sync request; implementation must remain behind v11 gates."""
    if sync_type not in {"insights", "leads", "campaigns"}:
        raise HTTPException(status_code=400, detail="sync_type must be insights, leads, or campaigns")
    return {
        "status": "queued_for_v11_workflow",
        "sync_type": sync_type,
        "org_id": org_id,
        "boundary": "n8n is auxiliary and cannot bypass v11 risk, approval, or license gates.",
    }
