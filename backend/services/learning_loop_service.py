"""Outcome labels and measurable learning loop.

Every decision can be labelled with its real-world outcome. Reports quantify
decision quality so improvements are measurable instead of anecdotal.
"""
from __future__ import annotations

import time
from typing import Any

from backend.services.state_repository import list_state, save_state

_NAMESPACE = "learning"


def record_outcome(
    project: str,
    decision: str,
    outcome: str,
    *,
    correct: bool | None = None,
    score: float = 0.0,
    note: str = "",
) -> dict[str, Any]:
    key = f"{project}::{int(time.time() * 1000)}"
    record = {
        "project": project,
        "decision": decision,
        "outcome": outcome,
        "correct": correct,
        "score": score,
        "note": note,
    }
    save_state(key, record, namespace=_NAMESPACE)
    return {"ok": True, "key": key, **record}


def outcomes() -> list[dict[str, Any]]:
    return [r["payload"] for r in list_state(namespace=_NAMESPACE)]


def report() -> dict[str, Any]:
    rows = outcomes()
    labelled = [r for r in rows if isinstance(r.get("correct"), bool)]
    correct = sum(1 for r in labelled if r["correct"])
    scores = [float(r.get("score") or 0) for r in rows]
    return {
        "ok": True,
        "total": len(rows),
        "labelled": len(labelled),
        "correct": correct,
        "accuracy": (correct / len(labelled)) if labelled else None,
        "average_score": (sum(scores) / len(scores)) if scores else 0.0,
        "by_project": {p: sum(1 for r in rows if r.get("project") == p) for p in {r.get("project") for r in rows}},
    }
