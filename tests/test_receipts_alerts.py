from __future__ import annotations

from pathlib import Path

import pytest

from backend.services import state_repository as repo
from backend.services import event_bus
from backend.services.alert_service import alerts, send as send_alert
from backend.services.approval_receipt_service import issue_receipt, list_receipts, verify_receipt


@pytest.fixture
def db(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CLOUD_OS_DATABASE_URL", f"sqlite:///{tmp_path / 'state.db'}")
    monkeypatch.delenv("CLOUD_OS_ALERT_WEBHOOK", raising=False)
    monkeypatch.setenv("CLOUD_OS_RECEIPT_SECRET", "test-secret")
    monkeypatch.setattr("backend.services.alert_service.ALERT_LOG", tmp_path / "alerts.log")
    repo.reset_engine()
    event_bus.reset_subscribers()
    yield tmp_path
    repo.reset_engine()
    event_bus.reset_subscribers()


def test_receipt_issue_and_verify(db):
    receipt = issue_receipt("Demo", "approve", "owner", verified=True)
    assert receipt["id"] and receipt["signature"]
    result = verify_receipt(receipt["id"])
    assert result["ok"] is True
    assert result["receipt"]["project"] == "Demo"
    assert len(list_receipts()) == 1


def test_receipt_tamper_detected(db):
    receipt = issue_receipt("Demo", "approve", "owner", verified=True)
    stored = repo.load_state(f"receipt::{receipt['id']}", namespace="approval_receipts")
    stored["decision"] = "reject"
    repo.save_state(f"receipt::{receipt['id']}", stored, namespace="approval_receipts")
    assert verify_receipt(receipt["id"])["ok"] is False


def test_alert_dedup_and_list(db):
    first = send_alert("High risk", "Customs exposure", severity="warning")
    assert "file" in first["channels"]
    second = send_alert("High risk", "Customs exposure", severity="warning")
    assert "deduplicated" in second["channels"]
    assert len(alerts()) == 1


def test_event_bus_triggers_alert(db, monkeypatch):
    calls = []
    monkeypatch.setenv("CLOUD_OS_ALERT_EVENTS", "risk.detected")
    monkeypatch.setattr("backend.services.alert_service.send", lambda *a, **k: calls.append(a) or {"ok": True})
    event_bus.publish("risk.detected", {"level": "high"})
    assert calls and calls[0][0] == "Event: risk.detected"
