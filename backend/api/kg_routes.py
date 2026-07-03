"""v12 Knowledge Graph API routes — entities, relations, queries, insights."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from backend.models.knowledge_graph import EntityType, RelationType
from backend.services.knowledge_graph_service import (
    create_entity,
    create_relation,
    discover_market_opportunities,
    find_alternative_suppliers,
    find_entity,
    trace_supply_chain_risk,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/kg", tags=["knowledge-graph"])


@router.post("/entities")
async def create_entity_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    entity = create_entity(
        name=body["name"],
        entity_type=EntityType(body.get("type", "company")),
        properties=body.get("properties", {}),
        aliases=body.get("aliases", []),
        source=body.get("source", "api"),
    )
    return {"entity_id": entity.id, "name": entity.name, "type": entity.type.value}


@router.get("/entities/search")
async def search_entity(name: str) -> dict[str, Any]:
    entity = find_entity(name)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return {
        "id": entity.id,
        "name": entity.name,
        "type": entity.type.value,
        "properties": entity.properties,
        "aliases": entity.aliases,
    }


@router.post("/relations")
async def create_relation_endpoint(request: Request) -> dict[str, Any]:
    body = await request.json()
    relation = create_relation(
        source_id=body["source_id"],
        target_id=body["target_id"],
        relation_type=RelationType(body.get("type", "supplies")),
        properties=body.get("properties", {}),
        source=body.get("source", "api"),
    )
    return {"relation_id": relation.id, "type": relation.type.value}


@router.get("/suppliers/alternatives")
async def alternative_suppliers(product: str, top_k: int = 10) -> dict[str, Any]:
    results = find_alternative_suppliers(product, top_k)
    return {"product": product, "alternatives": results}


@router.get("/risk/trace")
async def trace_risk(location: str, max_depth: int = 4) -> dict[str, Any]:
    insights = trace_supply_chain_risk(location, max_depth)
    return {"event_location": location, "depth": max_depth, "insights": [
        {"title": i.title, "description": i.description, "confidence": i.confidence}
        for i in insights
    ]}


@router.get("/opportunities")
async def market_opportunities(industry: str, country: str | None = None) -> dict[str, Any]:
    insights = discover_market_opportunities(industry, country)
    return {"industry": industry, "opportunities": [
        {"title": i.title, "description": i.description, "action": i.suggested_action}
        for i in insights
    ]}
