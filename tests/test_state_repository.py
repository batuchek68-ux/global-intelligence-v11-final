from __future__ import annotations

import time
from pathlib import Path

import pytest

from backend.services import state_repository as repo
from backend.services import cache_service as cache


@pytest.fixture
def db(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CLOUD_OS_DATABASE_URL", f"sqlite:///{tmp_path / 'state.db'}")
    repo.reset_engine()
    yield tmp_path
    repo.reset_engine()


def test_save_load_and_versioning(db):
    first = repo.save_state("last_run", {"count": 1})
    assert first["version"] == 1
    second = repo.save_state("last_run", {"count": 2})
    assert second["version"] == 2
    assert repo.load_state("last_run")["count"] == 2


def test_tenant_isolation(db):
    repo.save_state("note", {"v": "A"}, tenant_id="team-a")
    repo.save_state("note", {"v": "B"}, tenant_id="team-b")
    assert repo.load_state("note", tenant_id="team-a")["v"] == "A"
    assert repo.load_state("note", tenant_id="team-b")["v"] == "B"
    assert len(repo.list_state(tenant_id="team-a")) == 1


def test_persist_run_summary_and_export(db):
    repo.persist_run_summary({"project_count": 2, "case_count": 2})
    assert repo.load_state("last_run", namespace="operations")["project_count"] == 2
    out = repo.export_to_json(db / "export")
    assert out["ok"] is True
    assert out["exported"] >= 1
    assert (db / "export" / "operations__last_run.json").exists()


def test_health(db):
    assert repo.health()["ok"] is True


def test_cache_ttl(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    cache._LOCAL.clear()
    cache.set("k", "v", ttl=1)
    assert cache.get("k") == "v"
    cache.delete("k")
    assert cache.get("k") is None
    cache.set("short", 1, ttl=0)
    time.sleep(0.02)
    assert cache.get("short") is None
