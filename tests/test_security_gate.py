from __future__ import annotations

from pathlib import Path

import pytest

from backend.security.approval_gate import ApprovalGate, requires_human_approval
from backend.services.audit_service import append_audit, verify_audit_chain


def _gate(**kwargs):
    return ApprovalGate(secret="test-secret", **kwargs)


def test_approval_issue_and_verify():
    gate = _gate()
    token = gate.issue("contract_signing", "Demo", "approve", "owner")
    payload = gate.verify(token, action="contract_signing", project="Demo")
    assert payload and payload["decision"] == "approve" and payload["approver"] == "owner"


def test_tampered_token_is_rejected():
    gate = _gate()
    token = gate.issue("payment", "Demo", "approve", "owner")
    assert gate.verify(token[:-1] + ("a" if token[-1] != "a" else "b")) is None


def test_wrong_scope_is_rejected():
    gate = _gate()
    token = gate.issue("payment", "Demo", "approve", "owner")
    assert gate.verify(token, action="publishing") is None
    assert gate.verify(token, project="Other") is None


def test_expired_token_is_rejected():
    gate = _gate(ttl_seconds=-10)
    token = gate.issue("payment", "Demo", "approve", "owner")
    assert gate.verify(token) is None


def test_replay_is_rejected():
    gate = _gate()
    token = gate.issue("payment", "Demo", "approve", "owner")
    assert gate.verify(token) is not None
    assert gate.verify(token) is None


def test_risk_boundary():
    assert requires_human_approval("high", 0) is True
    assert requires_human_approval("low", 100000) is True
    assert requires_human_approval("low", 10) is False


def test_audit_chain_verifies_and_detects_tampering(tmp_path: Path):
    path = tmp_path / "audit.log"
    append_audit("A", "DONE", "first", path=path)
    append_audit("B", "DONE", "second", path=path)
    result = verify_audit_chain(path)
    assert result["ok"] is True
    assert result["chained"] == 2

    lines = path.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("first", "tampered")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert verify_audit_chain(path)["ok"] is False


def test_legacy_audit_lines_are_counted(tmp_path: Path):
    path = tmp_path / "audit.log"
    path.write_text("2026-01-01 | Codex | LEGACY | DONE\n", encoding="utf-8")
    append_audit("NEW", "DONE", "ok", path=path)
    result = verify_audit_chain(path)
    assert result["legacy"] == 1
    assert result["chained"] == 1
    assert result["ok"] is True


def test_approval_endpoint_requires_signed_token(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.api.main import app

    monkeypatch.setenv("CLOUD_OS_APPROVAL_SECRET", "endpoint-test-secret")
    client = TestClient(app)
    payload = {"decision": "approve", "project": "Demo", "note": "ok"}
    assert client.post("/v1/approvals/decision", json=payload).status_code == 403

    gate = ApprovalGate(secret="endpoint-test-secret")
    token = gate.issue("approval_decision", "Demo", "approve", "owner")
    payload["approval_token"] = token
    response = client.post("/v1/approvals/decision", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["verified"] is True
    assert body["approver"] == "owner"


def test_approval_endpoint_legacy_mode(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.api.main import app

    monkeypatch.delenv("CLOUD_OS_APPROVAL_SECRET", raising=False)
    response = TestClient(app).post(
        "/v1/approvals/decision", json={"decision": "approve", "project": "Demo"}
    )
    assert response.status_code == 200
    assert response.json()["verified"] is False
