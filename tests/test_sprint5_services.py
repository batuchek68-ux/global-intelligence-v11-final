from __future__ import annotations

from pathlib import Path

import pytest

from backend.services import state_repository as repo
from backend.services import event_bus, learning_loop_service as learning
from backend.services.agent_debate_service import debate


@pytest.fixture
def db(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CLOUD_OS_DATABASE_URL", f"sqlite:///{tmp_path / 'state.db'}")
    monkeypatch.setenv("OPS_USE_LLM", "0")
    repo.reset_engine()
    event_bus.reset_subscribers()
    yield tmp_path
    repo.reset_engine()
    event_bus.reset_subscribers()


def test_event_bus_publish_and_subscribe(db):
    seen = []
    event_bus.subscribe("risk.detected", lambda e: seen.append(e))
    event = event_bus.publish("risk.detected", {"level": "high"})
    assert event["type"] == "risk.detected"
    assert seen and seen[0]["id"] == event["id"]
    events = event_bus.list_events("risk.detected")
    assert len(events) >= 1


def test_debate_without_evidence_requires_human(db):
    result = debate("Customs clearance will be fast", [], risk="high")
    assert result["ok"] is True
    assert result["consensus"] is False
    assert result["requires_human"] is True
    assert set(result["perspectives"]) == {"analyst", "risk_gate", "auditor"}


def test_debate_with_evidence(db):
    result = debate("Port project exists", ["official government tender notice"], risk="low")
    assert result["consensus"] is True
    assert result["confidence"] > 45
    assert result["requires_human"] is False


def test_learning_report(db):
    learning.record_outcome("Demo", "approve", "won contract", correct=True, score=90)
    learning.record_outcome("Demo", "approve", "lost contract", correct=False, score=20)
    report = learning.report()
    assert report["total"] == 2
    assert report["labelled"] == 2
    assert report["accuracy"] == 0.5
    assert report["average_score"] == 55.0
