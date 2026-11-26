from __future__ import annotations

import pytest

from backend.services import rag_benchmark_service as bench


def test_default_gold_set():
    gold = bench.default_gold_set()
    assert len(gold) >= 5
    assert all(c.get("query") and c.get("expect") for c in gold)


def test_evaluate_uses_local_index(monkeypatch):
    monkeypatch.setattr(bench, "REPORT_DIR", __import__("pathlib").Path(".tmp-benchmark"))
    monkeypatch.setattr(bench.knowledge, "stats", lambda: {"ok": True, "count": 10})
    monkeypatch.setattr(
        bench.knowledge, "query",
        lambda q, n: {"ok": True, "results": [{"text": "kazakhstan customs documents", "metadata": {"source": "wiki", "path": "wiki/test.md"}}]},
    )
    report = bench.evaluate()
    assert report["ok"] is True
    assert report["total"] == len(bench.load_gold_set())
    assert 0 <= report["accuracy"] <= 1
    assert report["index"]["count"] == 10
