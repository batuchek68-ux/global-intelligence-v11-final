"""v12 Knowledge Graph data models — entities, relationships, queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EntityType(Enum):
    COMPANY = "company"
    PRODUCT = "product"
    INDUSTRY = "industry"
    COUNTRY = "country"
    PORT = "port"
    CERTIFICATION = "certification"
    PROJECT = "project"
    PERSON = "person"
    REGULATION = "regulation"
    EVENT = "event"


class RelationType(Enum):
    SUPPLIES = "supplies"
    PURCHASES = "purchases"
    COMPETES_WITH = "competes_with"
    PARTNERS_WITH = "partners_with"
    LOCATED_IN = "located_in"
    CERTIFIED_BY = "certified_by"
    OWNS = "owns"
    REGULATES = "regulates"
    AFFECTS = "affects"
    PARTICIPATES_IN = "participates_in"


@dataclass
class Entity:
    id: str
    name: str
    type: EntityType
    properties: dict[str, Any] = field(default_factory=dict)
    aliases: list[str] = field(default_factory=list)
    confidence: float = 1.0         # extraction confidence 0-1
    source: str = ""                 # data source
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Relation:
    id: str
    source_id: str                   # from entity
    target_id: str                   # to entity
    type: RelationType
    properties: dict[str, Any] = field(default_factory=dict)  # e.g. {"volume": "1000 tons", "since": "2020"}
    confidence: float = 1.0
    source: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class GraphQuery:
    """A structured query against the knowledge graph."""
    id: str
    query_type: str = ""             # "entity_lookup", "path_finding", "subgraph", "insight"
    entity_ids: list[str] = field(default_factory=list)
    relation_types: list[str] = field(default_factory=list)
    max_depth: int = 3
    filters: dict[str, Any] = field(default_factory=dict)
    natural_language: str = ""


@dataclass
class GraphPath:
    """A path between two entities in the knowledge graph."""
    start_entity: str
    end_entity: str
    path: list[dict[str, str]] = field(default_factory=list)  # [{"entity": ..., "relation": ...}, ...]
    length: int = 0
    total_confidence: float = 0.0


@dataclass
class GraphInsight:
    """An insight derived from the knowledge graph."""
    id: str
    title: str
    description: str
    insight_type: str = ""           # "opportunity", "risk", "trend", "connection"
    entities: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    actionable: bool = False
    suggested_action: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
