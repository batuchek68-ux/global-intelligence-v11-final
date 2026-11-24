from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_infra_compose_defines_postgres_and_redis():
    text = (ROOT / "docker-compose.infra.yml").read_text(encoding="utf-8")
    assert "postgres:15-alpine" in text
    assert "redis:7-alpine" in text
    assert "5432:5432" in text
    assert "6379:6379" in text


def test_start_infra_script_exists():
    assert (ROOT / "scripts" / "start-infra.ps1").exists()
