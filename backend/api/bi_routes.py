"""v12 BI Analytics API routes — dashboards, reports, metrics."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.services.bi_analytics_service import generate_bi_report, get_dashboard_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/bi", tags=["bi-analytics"])


@router.get("/dashboard")
async def dashboard() -> dict[str, Any]:
    return get_dashboard_summary()


@router.get("/dashboard/overview")
async def dashboard_overview() -> dict[str, Any]:
    data = get_dashboard_summary()
    return data["overview"]


@router.get("/dashboard/trade-volume")
async def dashboard_trade_volume() -> dict[str, Any]:
    data = get_dashboard_summary()
    return data["trade_volume"]


@router.get("/dashboard/pipeline")
async def dashboard_pipeline() -> dict[str, Any]:
    data = get_dashboard_summary()
    return data["pipeline"]


@router.get("/dashboard/risk")
async def dashboard_risk() -> dict[str, Any]:
    data = get_dashboard_summary()
    return data["risk"]


@router.get("/dashboard/financial")
async def dashboard_financial() -> dict[str, Any]:
    data = get_dashboard_summary()
    return data["financial"]


@router.get("/dashboard/trends")
async def dashboard_trends() -> dict[str, Any]:
    data = get_dashboard_summary()
    return data["trends"]


@router.post("/reports/generate")
async def generate_report(request: Request) -> dict[str, Any]:
    body = await request.json()
    fmt = body.get("format", "json")
    path = generate_bi_report(format=fmt)
    return {"ok": True, "path": str(path), "format": fmt}
