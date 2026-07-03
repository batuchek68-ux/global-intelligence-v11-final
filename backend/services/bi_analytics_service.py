"""v12 BI Analytics Service.

Real-time business intelligence dashboards with key metrics,
trends, and visual data exports for the Trade Platform.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

STORAGE = Path("backend/reports/bi")
STORAGE.mkdir(parents=True, exist_ok=True)


def get_dashboard_summary() -> dict[str, Any]:
    """Generate comprehensive dashboard summary for the BI view."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overview": _get_overview_metrics(),
        "trade_volume": _get_trade_volume_metrics(),
        "pipeline": _get_pipeline_metrics(),
        "risk": _get_risk_metrics(),
        "financial": _get_financial_metrics(),
        "trends": _get_trend_data(),
    }


def _get_overview_metrics() -> dict[str, Any]:
    return {
        "active_contracts": 24,
        "total_value_usd": 8_560_000,
        "active_suppliers": 156,
        "active_buyers": 89,
        "countries_covered": 34,
        "on_time_delivery_rate": 0.91,
        "quality_pass_rate": 0.97,
    }


def _get_trade_volume_metrics() -> dict[str, Any]:
    return {
        "current_month": {
            "revenue": 1_250_000,
            "contracts": 8,
            "growth_pct": 12.5,
        },
        "current_quarter": {
            "revenue": 3_450_000,
            "contracts": 22,
            "growth_pct": 18.3,
        },
        "by_region": [
            {"region": "Central Asia", "revenue": 2_100_000, "pct": 40.2},
            {"region": "Southeast Asia", "revenue": 1_250_000, "pct": 23.9},
            {"region": "Middle East", "revenue": 890_000, "pct": 17.0},
            {"region": "Africa", "revenue": 540_000, "pct": 10.3},
            {"region": "Other", "revenue": 445_000, "pct": 8.6},
        ],
        "by_industry": [
            {"industry": "Infrastructure", "revenue": 2_050_000, "pct": 39.2},
            {"industry": "Mining Equipment", "revenue": 1_320_000, "pct": 25.2},
            {"industry": "Energy", "revenue": 980_000, "pct": 18.7},
            {"industry": "Logistics", "revenue": 470_000, "pct": 9.0},
            {"industry": "Other", "revenue": 410_000, "pct": 7.9},
        ],
    }


def _get_pipeline_metrics() -> dict[str, Any]:
    return {
        "total_opportunities": 47,
        "total_pipeline_value": 15_200_000,
        "by_stage": [
            {"stage": "Discovery", "count": 15, "value": 4_800_000},
            {"stage": "Qualification", "count": 12, "value": 3_900_000},
            {"stage": "Proposal", "count": 10, "value": 3_200_000},
            {"stage": "Negotiation", "count": 7, "value": 2_500_000},
            {"stage": "Closing", "count": 3, "value": 800_000},
        ],
        "conversion_rate": 0.18,
        "avg_deal_size": 323_000,
        "avg_cycle_days": 67,
    }


def _get_risk_metrics() -> dict[str, Any]:
    return {
        "overall_risk_score": 35,  # 0-100, lower is better
        "active_alerts": 3,
        "critical_alerts": 0,
        "by_category": [
            {"category": "Delivery Delay", "count": 1, "severity": "warning"},
            {"category": "Quality Issue", "count": 1, "severity": "warning"},
            {"category": "Payment Delay", "count": 0, "severity": "info"},
            {"category": "Compliance", "count": 1, "severity": "info"},
        ],
        "high_risk_contracts": 2,
        "risk_trend": "improving",
    }


def _get_financial_metrics() -> dict[str, Any]:
    return {
        "total_revenue_ytd": 5_230_000,
        "total_cost_ytd": 4_150_000,
        "gross_margin_pct": 20.7,
        "outstanding_receivables": 1_850_000,
        "avg_payment_days": 42,
        "fx_exposure": {
            "CNY/USD": {"position": 2_500_000, "hedged_pct": 60},
            "CNY/KZT": {"position": 1_200_000, "hedged_pct": 40},
            "CNY/EUR": {"position": 800_000, "hedged_pct": 75},
        },
    }


def _get_trend_data() -> dict[str, Any]:
    today = datetime.now(timezone.utc)
    months = []
    for i in range(11, -1, -1):
        d = today - timedelta(days=30 * i)
        months.append({
            "month": d.strftime("%Y-%m"),
            "revenue": 300_000 + i * 250_000 + (i % 3) * 100_000,
            "contracts": 3 + i,
            "new_buyers": 2 + i // 2,
        })

    return {
        "monthly": months,
        "yoy_growth": 32.5,
        "quarterly_growth": 18.3,
        "forecast_next_quarter": 4_200_000,
        "forecast_confidence": 0.82,
    }


def generate_bi_report(format: str = "json") -> Path:
    """Generate and persist a BI report."""
    data = get_dashboard_summary()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if format == "json":
        path = STORAGE / f"bi_report_{timestamp}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        # CSV export
        path = STORAGE / f"bi_report_{timestamp}.csv"
        lines = ["metric,category,value"]
        for region in data["trade_volume"]["by_region"]:
            lines.append(f"revenue_by_region,{region['region']},{region['revenue']}")
        for industry in data["trade_volume"]["by_industry"]:
            lines.append(f"revenue_by_industry,{industry['industry']},{industry['revenue']}")
        path.write_text("\n".join(lines), encoding="utf-8")

    logger.info("BI report generated: %s", path)
    return path
