"""v12 Knowledge Graph Service.

Neo4j-backed knowledge graph for entity-relationship reasoning:
- Alternative supplier discovery
- Supply chain risk propagation
- Market opportunity mapping
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.integrations.neo4j_connector import get_neo4j_connector
from backend.models.knowledge_graph import (
    Entity,
    EntityType,
    GraphInsight,
    GraphPath,
    GraphQuery,
    Relation,
    RelationType,
)

logger = logging.getLogger(__name__)

STORAGE = Path("backend/memory/knowledge_graph")
STORAGE.mkdir(parents=True, exist_ok=True)


def create_entity(
    name: str,
    entity_type: EntityType,
    properties: dict[str, Any] | None = None,
    aliases: list[str] | None = None,
    source: str = "manual",
) -> Entity:
    """Create a new entity in the knowledge graph."""
    entity = Entity(
        id=f"ent_{uuid.uuid4().hex[:12]}",
        name=name,
        type=entity_type,
        properties=properties or {},
        aliases=aliases or [],
        source=source,
    )
    _save_entity(entity)
    logger.info("KG: created entity %s (%s)", name, entity_type.value)
    return entity


def create_relation(
    source_id: str,
    target_id: str,
    relation_type: RelationType,
    properties: dict[str, Any] | None = None,
    source: str = "manual",
) -> Relation:
    """Create a relationship between two entities."""
    relation = Relation(
        id=f"rel_{uuid.uuid4().hex[:12]}",
        source_id=source_id,
        target_id=target_id,
        type=relation_type,
        properties=properties or {},
        source=source,
    )
    _save_relation(relation)
    logger.info("KG: created relation %s --[%s]--> %s", source_id, relation_type.value, target_id)
    return relation


def find_entity(name: str) -> Entity | None:
    """Find an entity by name or alias."""
    for f in STORAGE.glob("entity_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            entity_name = data.get("name", "")
            aliases = data.get("aliases", [])
            if entity_name.lower() == name.lower() or name.lower() in [a.lower() for a in aliases]:
                return Entity(
                    id=data["id"],
                    name=data["name"],
                    type=EntityType(data["type"]),
                    properties=data.get("properties", {}),
                    aliases=aliases,
                    source=data.get("source", ""),
                )
        except Exception:
            continue
    return None


def find_alternative_suppliers(product: str, top_k: int = 10) -> list[dict[str, Any]]:
    """Discover alternative suppliers for a given product."""
    entities = _load_all_entities()
    relations = _load_all_relations()

    product_entity = next((e for e in entities if e.name.lower() == product.lower()), None)
    if not product_entity:
        return []

    supplier_relations = [
        r for r in relations
        if r.type == RelationType.SUPPLIES and r.target_id == product_entity.id
    ]

    results: list[dict[str, Any]] = []
    for rel in supplier_relations:
        supplier = _get_entity_by_id(entities, rel.source_id)
        if supplier:
            results.append({
                "supplier_name": supplier.name,
                "supplier_type": supplier.type.value,
                "country": supplier.properties.get("country", "Unknown"),
                "relation_strength": rel.confidence,
                "since": rel.properties.get("since", "Unknown"),
            })

    return sorted(results, key=lambda r: r["relation_strength"], reverse=True)[:top_k]


def trace_supply_chain_risk(event_location: str, max_depth: int = 4) -> list[GraphInsight]:
    """Trace how an event at a location propagates risk through the supply chain."""
    entities = _load_all_entities()
    relations = _load_all_relations()

    location_entity = next((e for e in entities if e.name.lower() == event_location.lower()), None)
    if not location_entity:
        return []

    insights: list[GraphInsight] = []
    visited: set[str] = {location_entity.id}

    # BFS propagation
    current_layer = [location_entity.id]
    for depth in range(max_depth):
        next_layer: list[str] = []
        for current_id in current_layer:
            connected = [r for r in relations if r.source_id == current_id or r.target_id == current_id]
            for rel in connected:
                other_id = rel.target_id if rel.source_id == current_id else rel.source_id
                if other_id not in visited:
                    visited.add(other_id)
                    next_layer.append(other_id)
                    other_entity = _get_entity_by_id(entities, other_id)
                    if other_entity and other_entity.type in (EntityType.COMPANY, EntityType.PRODUCT, EntityType.PORT):
                        insights.append(GraphInsight(
                            id=f"ins_{uuid.uuid4().hex[:12]}",
                            title=f"Risk chain: {event_location} → {other_entity.name}",
                            description=f"Event at {event_location} may affect {other_entity.name} via {rel.type.value} (depth {depth + 1}).",
                            insight_type="risk",
                            entities=[event_location, other_entity.name],
                            confidence=max(0.3, rel.confidence * (1 - depth * 0.2)),
                        ))
        current_layer = next_layer

    return insights[:20]


def discover_market_opportunities(industry: str, country: str | None = None) -> list[GraphInsight]:
    """Discover market opportunities based on graph reasoning."""
    insights: list[GraphInsight] = []
    entities = _load_all_entities()
    relations = _load_all_relations()

    industry_entity = next((e for e in entities if e.name.lower() == industry.lower()), None)
    if not industry_entity:
        return []

    # Find products in this industry
    industry_relations = [
        r for r in relations
        if (r.source_id == industry_entity.id or r.target_id == industry_entity.id)
        and r.type in (RelationType.AFFECTS, RelationType.PARTICIPATES_IN)
    ]

    for rel in industry_relations:
        other_id = rel.target_id if rel.source_id == industry_entity.id else rel.source_id
        other = _get_entity_by_id(entities, other_id)
        if other:
            insights.append(GraphInsight(
                id=f"ins_{uuid.uuid4().hex[:12]}",
                title=f"Opportunity in {other.name}",
                description=f"Increased demand in {industry} sector driving opportunities for {other.name}.",
                insight_type="opportunity",
                entities=[industry, other.name],
                confidence=rel.confidence,
                actionable=True,
                suggested_action=f"Explore {other.name} sourcing opportunities in {industry} market.",
            ))

    return insights


# ── Persistence Helpers ────────────────────────────────────────────

def _save_entity(entity: Entity) -> None:
    (STORAGE / f"entity_{entity.id}.json").write_text(json.dumps({
        "id": entity.id,
        "name": entity.name,
        "type": entity.type.value,
        "properties": entity.properties,
        "aliases": entity.aliases,
        "confidence": entity.confidence,
        "source": entity.source,
        "created_at": entity.created_at.isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_relation(relation: Relation) -> None:
    (STORAGE / f"relation_{relation.id}.json").write_text(json.dumps({
        "id": relation.id,
        "source_id": relation.source_id,
        "target_id": relation.target_id,
        "type": relation.type.value,
        "properties": relation.properties,
        "confidence": relation.confidence,
        "source": relation.source,
        "created_at": relation.created_at.isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_all_entities() -> list[Entity]:
    entities: list[Entity] = []
    for f in STORAGE.glob("entity_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            entities.append(Entity(
                id=data["id"],
                name=data["name"],
                type=EntityType(data["type"]),
                properties=data.get("properties", {}),
                aliases=data.get("aliases", []),
                confidence=data.get("confidence", 1.0),
                source=data.get("source", ""),
            ))
        except Exception:
            continue
    return entities


def _load_all_relations() -> list[Relation]:
    relations: list[Relation] = []
    for f in STORAGE.glob("relation_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            relations.append(Relation(
                id=data["id"],
                source_id=data["source_id"],
                target_id=data["target_id"],
                type=RelationType(data["type"]),
                properties=data.get("properties", {}),
                confidence=data.get("confidence", 1.0),
                source=data.get("source", ""),
            ))
        except Exception:
            continue
    return relations


def _get_entity_by_id(entities: list[Entity], entity_id: str) -> Entity | None:
    return next((e for e in entities if e.id == entity_id), None)
