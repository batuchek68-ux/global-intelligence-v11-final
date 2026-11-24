"""Signed, durable approval receipts for owner decisions.

A receipt is the proof that a decision was recorded; it can be listed and
verified independently of the decision-hub UI.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from typing import Any

from backend.services.state_repository import list_state, save_state, load_state

_NAMESPACE = "approval_receipts"


def _secret() -> str:
    return os.getenv("CLOUD_OS_RECEIPT_SECRET") or os.getenv("CLOUD_OS_APPROVAL_SECRET") or "local-receipt-key"


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sign(payload: dict[str, Any]) -> str:
    return hmac.new(_secret().encode("utf-8"), _canonical(payload).encode("utf-8"), hashlib.sha256).hexdigest()


def issue_receipt(
    project: str,
    decision: str,
    approver: str,
    *,
    verified: bool,
    note: str = "",
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    core = {
        "project": project,
        "decision": decision,
        "approver": approver,
        "verified": bool(verified),
        "note": note,
        "created_at": now,
        "nonce": secrets.token_hex(8),
    }
    receipt_id = hashlib.sha256(_canonical(core).encode("utf-8")).hexdigest()[:16]
    receipt = {"id": receipt_id, **core, "status": "final"}
    receipt["signature"] = _sign(receipt)
    save_state(f"receipt::{receipt_id}", receipt, namespace=_NAMESPACE)
    return receipt


def get_receipt(receipt_id: str) -> dict[str, Any] | None:
    return load_state(f"receipt::{receipt_id}", namespace=_NAMESPACE)


def verify_receipt(receipt_id: str) -> dict[str, Any]:
    receipt = get_receipt(receipt_id)
    if not receipt:
        return {"ok": False, "reason": "not found"}
    signature = receipt.pop("signature", "")
    valid = hmac.compare_digest(signature, _sign(receipt)) if signature else False
    return {"ok": valid, "receipt": {**receipt, "signature": signature}}


def list_receipts(limit: int = 50) -> list[dict[str, Any]]:
    rows = list_state(namespace=_NAMESPACE)
    rows.sort(key=lambda r: r["updated_at"], reverse=True)
    return [r["payload"] for r in rows[:limit]]
