from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.services import knowledge_ingest_service as kis


@pytest.fixture
def knowledge_env(tmp_path: Path, monkeypatch):
    src = tmp_path / "sources"
    src.mkdir()
    (src / "kazakhstan.md").write_text(
        "# Kazakhstan customs\nKazakhstan customs clearance requires EAEU documents and port inspection.\n",
        encoding="utf-8",
    )
    (src / "wechat.md").write_text(
        "# WeChat favorite\nNegotiation notes about payment terms and guarantee for a port project.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("KNOWLEDGE_SOURCES", json.dumps({"demo": str(src)}))
    monkeypatch.setenv("KNOWLEDGE_CHROMA_DIR", str(tmp_path / "chroma"))
    return src


def test_build_and_query(knowledge_env):
    built = kis.build_index(reset=True)
    assert built["ok"] is True
    assert built["chunks"] >= 2
    stats = kis.stats()
    assert stats["count"] >= 2

    result = kis.query("Kazakhstan customs clearance", n=3)
    assert result["ok"] is True
    assert result["results"]
    assert result["results"][0]["metadata"]["source"] == "demo"


def test_incremental_build_skips_existing(knowledge_env):
    first = kis.build_index(reset=True, limit_per_source=2)
    before = kis.stats()["count"]
    second = kis.build_index(reset=False, limit_per_source=2)
    assert second["chunks"] == 0
    assert kis.stats()["count"] == before
    assert first["ok"] is True


def test_evaluate(knowledge_env):
    kis.build_index(reset=True)
    report = kis.evaluate([
        {"query": "port project guarantee", "expect_keywords": ["guarantee"], "n": 3},
    ])
    assert report["ok"] is True
    assert report["total"] == 1
    assert report["accuracy"] > 0
