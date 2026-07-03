"""v12 Neo4j Connector.

Graph database integration for the Knowledge Graph service.
Supports both real Neo4j connections and a local file-based fallback
for development without a running Neo4j instance.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FALLBACK_DIR = Path("backend/memory/knowledge_graph")
FALLBACK_DIR.mkdir(parents=True, exist_ok=True)


class Neo4jConnector:
    """Neo4j graph database connector with local fallback.

    Attempts to connect to a Neo4j instance; falls back to file-based
    storage when Neo4j is not available (development mode).
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
        database: str = "neo4j",
    ):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self._driver = None
        self._use_fallback = True
        self._try_connect()

    def _try_connect(self) -> None:
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            self._driver.verify_connectivity()
            self._use_fallback = False
            logger.info("Neo4j connected: %s", self.uri)
        except ImportError:
            logger.info("neo4j driver not installed; using file-based fallback")
        except Exception as exc:
            logger.info("Neo4j unavailable (%s); using file-based fallback", exc)

    def run_query(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Execute a Cypher query. Falls back to local search."""
        if not self._use_fallback and self._driver:
            return self._run_neo4j(cypher, parameters or {})
        return self._run_fallback_search(parameters or {})

    def _run_neo4j(self, cypher: str, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute against real Neo4j."""
        try:
            with self._driver.session(database=self.database) as session:
                result = session.run(cypher, parameters)
                return [record.data() for record in result]
        except Exception as exc:
            logger.warning("Neo4j query failed: %s; switching to fallback", exc)
            self._use_fallback = True
            return self._run_fallback_search(parameters)

    def _run_fallback_search(self, parameters: dict[str, Any]) -> list[dict[str, Any]]:
        """Search local file-based storage."""
        results: list[dict[str, Any]] = []

        entity_name = parameters.get("name", parameters.get("entity", ""))
        if entity_name:
            for f in FALLBACK_DIR.glob("entity_*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if entity_name.lower() in data.get("name", "").lower():
                        results.append(data)
                except Exception:
                    continue

        return results

    def create_node(self, labels: list[str], properties: dict[str, Any]) -> dict[str, Any]:
        """Create a graph node."""
        if not self._use_fallback and self._driver:
            return self._create_neo4j_node(labels, properties)
        return {"status": "fallback", "labels": labels, "properties": properties}

    def _create_neo4j_node(self, labels: list[str], properties: dict[str, Any]) -> dict[str, Any]:
        label_str = ":" + ":".join(labels)
        prop_str = ", ".join(f"{k}: ${k}" for k in properties)
        cypher = f"CREATE (n{label_str} {{{prop_str}}}) RETURN n"
        try:
            with self._driver.session(database=self.database) as session:
                result = session.run(cypher, properties)
                return result.single().data()
        except Exception as exc:
            logger.warning("Neo4j node creation failed: %s", exc)
            return {"status": "failed", "error": str(exc)}

    def health_check(self) -> dict[str, Any]:
        if self._use_fallback:
            entity_count = len(list(FALLBACK_DIR.glob("entity_*.json")))
            return {"status": "fallback", "mode": "file_based", "entities": entity_count}

        try:
            with self._driver.session(database=self.database) as session:
                result = session.run("MATCH (n) RETURN count(n) AS count")
                count = result.single()["count"]
                return {"status": "connected", "uri": self.uri, "node_count": count}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def close(self) -> None:
        if self._driver:
            self._driver.close()


_neo4j: Neo4jConnector | None = None


def get_neo4j_connector(
    uri: str = "bolt://localhost:7687",
    username: str = "neo4j",
    password: str = "password",
) -> Neo4jConnector:
    global _neo4j
    if _neo4j is None:
        _neo4j = Neo4jConnector(uri=uri, username=username, password=password)
    return _neo4j
