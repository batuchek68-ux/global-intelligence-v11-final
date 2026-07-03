"""v12 Kafka Connector.

Event bus integration for asynchronous service-to-service communication.
Supports real Kafka clusters and an in-memory fallback for development.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

FALLBACK_DIR = Path("backend/memory/events")
FALLBACK_DIR.mkdir(parents=True, exist_ok=True)


class KafkaConnector:
    """Kafka event bus connector with in-memory fallback.

    Publishes and subscribes to named topics. When Kafka is unavailable,
    uses an in-memory broker with file persistence.
    """

    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        client_id: str = "global-intelligence-v12",
    ):
        self.bootstrap_servers = bootstrap_servers
        self.client_id = client_id
        self._producer = None
        self._consumer = None
        self._use_fallback = True
        self._subscribers: dict[str, list[Callable[[dict[str, Any]], None]]] = {}
        self._event_log: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._try_connect()

    def _try_connect(self) -> None:
        try:
            from kafka import KafkaProducer, KafkaConsumer
            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            )
            self._consumer = KafkaConsumer(
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                auto_offset_reset="latest",
                group_id=self.client_id,
            )
            self._use_fallback = False
            logger.info("Kafka connected: %s", self.bootstrap_servers)
        except ImportError:
            logger.info("kafka-python not installed; using in-memory fallback")
        except Exception as exc:
            logger.info("Kafka unavailable (%s); using in-memory fallback", exc)

    def publish(self, topic: str, event: dict[str, Any]) -> bool:
        """Publish an event to a topic."""
        event["_topic"] = topic
        event["_timestamp"] = datetime.now(timezone.utc).isoformat()

        if not self._use_fallback and self._producer:
            return self._publish_kafka(topic, event)

        return self._publish_fallback(topic, event)

    def _publish_kafka(self, topic: str, event: dict[str, Any]) -> bool:
        try:
            future = self._producer.send(topic, event)
            future.get(timeout=10)
            logger.debug("Kafka event published to %s", topic)
            return True
        except Exception as exc:
            logger.warning("Kafka publish failed: %s; switching to fallback", exc)
            self._use_fallback = True
            return self._publish_fallback(topic, event)

    def _publish_fallback(self, topic: str, event: dict[str, Any]) -> bool:
        with self._lock:
            self._event_log.append(event)
            self._persist_event(event)

            subscribers = self._subscribers.get(topic, [])
            for callback in subscribers:
                try:
                    callback(event)
                except Exception as exc:
                    logger.warning("Subscriber callback failed for %s: %s", topic, exc)

        logger.debug("In-memory event published to %s", topic)
        return True

    def subscribe(self, topic: str, callback: Callable[[dict[str, Any]], None]) -> None:
        """Subscribe to a topic with a callback function."""
        with self._lock:
            self._subscribers.setdefault(topic, []).append(callback)
        logger.info("Subscribed to topic: %s", topic)

    def unsubscribe(self, topic: str, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            if topic in self._subscribers and callback in self._subscribers[topic]:
                self._subscribers[topic].remove(callback)

    def get_events(self, topic: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieve recent events, optionally filtered by topic."""
        with self._lock:
            events = self._event_log[-limit:]
            if topic:
                return [e for e in events if e.get("_topic") == topic]
            return events

    def health_check(self) -> dict[str, Any]:
        if self._use_fallback:
            return {
                "status": "fallback",
                "mode": "in_memory",
                "total_events": len(self._event_log),
                "active_topics": list(self._subscribers.keys()),
            }
        return {"status": "connected", "bootstrap_servers": self.bootstrap_servers}

    def _persist_event(self, event: dict[str, Any]) -> None:
        try:
            path = FALLBACK_DIR / "events.jsonl"
            with open(path, "a", encoding="utf-8") as fp:
                fp.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def close(self) -> None:
        if self._producer:
            self._producer.close()
        if self._consumer:
            self._consumer.close()


_kafka: KafkaConnector | None = None


def get_kafka_connector(bootstrap_servers: str = "localhost:9092") -> KafkaConnector:
    global _kafka
    if _kafka is None:
        _kafka = KafkaConnector(bootstrap_servers=bootstrap_servers)
    return _kafka
