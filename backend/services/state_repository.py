"""Transactional operating-state store (SQLite locally, PostgreSQL via DATABASE_URL).

Replaces concurrent read-modify-write of JSON files with row-level transactions.
File exports remain available for Obsidian/human review.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import Column, Integer, String, Text, create_engine, select, text
from sqlalchemy.orm import declarative_base, sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = BACKEND_ROOT / "memory" / "state.db"
Base = declarative_base()


class StateEntry(Base):
    __tablename__ = "state_entries"
    id = Column(Integer, primary_key=True)
    tenant_id = Column(String(128), default="owner", nullable=False)
    namespace = Column(String(128), default="default", nullable=False)
    key = Column(String(256), nullable=False)
    payload = Column(Text, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    updated_at = Column(String(64), nullable=False)


def _engine():
    url = os.getenv("CLOUD_OS_DATABASE_URL")
    if not url:
        DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    return create_engine(url, future=True)


_ENGINE = None
_SESSION = None


def reset_engine() -> None:
    """Test/maintenance helper to rebind to a new DATABASE_URL."""
    global _ENGINE, _SESSION
    _ENGINE = None
    _SESSION = None


def engine():
    global _ENGINE, _SESSION
    if _ENGINE is None:
        _ENGINE = _engine()
        Base.metadata.create_all(_ENGINE)
        _SESSION = sessionmaker(bind=_ENGINE, expire_on_commit=False, future=True)
    return _ENGINE


@contextmanager
def session() -> Iterator[Any]:
    engine()
    with _SESSION() as s:
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def save_state(key: str, payload: Any, *, tenant_id: str = "owner", namespace: str = "default") -> dict[str, Any]:
    with session() as s:
        row = s.scalar(
            select(StateEntry).where(
                StateEntry.tenant_id == tenant_id,
                StateEntry.namespace == namespace,
                StateEntry.key == key,
            )
        )
        if row is None:
            row = StateEntry(tenant_id=tenant_id, namespace=namespace, key=key, payload="{}", version=0, updated_at=_now())
            s.add(row)
            s.flush()
        row.payload = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        row.version = int(row.version) + 1
        row.updated_at = _now()
        s.flush()
        return {"ok": True, "key": key, "version": row.version, "tenant_id": tenant_id, "namespace": namespace}


def load_state(key: str, *, default: Any = None, tenant_id: str = "owner", namespace: str = "default") -> Any:
    with session() as s:
        row = s.scalar(
            select(StateEntry).where(
                StateEntry.tenant_id == tenant_id,
                StateEntry.namespace == namespace,
                StateEntry.key == key,
            )
        )
        return json.loads(row.payload) if row else default


def list_state(*, tenant_id: str | None = None, namespace: str | None = None) -> list[dict[str, Any]]:
    with session() as s:
        stmt = select(StateEntry)
        if tenant_id:
            stmt = stmt.where(StateEntry.tenant_id == tenant_id)
        if namespace:
            stmt = stmt.where(StateEntry.namespace == namespace)
        rows = s.scalars(stmt.order_by(StateEntry.updated_at.desc())).all()
        return [
            {"key": r.key, "tenant_id": r.tenant_id, "namespace": r.namespace,
             "version": r.version, "updated_at": r.updated_at, "payload": json.loads(r.payload)}
            for r in rows
        ]


def persist_run_summary(summary: dict[str, Any], *, tenant_id: str = "owner") -> dict[str, Any]:
    """Store the daily cycle summary transactionally; safe under concurrent runs."""
    return save_state("last_run", summary, tenant_id=tenant_id, namespace="operations")


def export_to_json(target_dir: Path) -> dict[str, Any]:
    """Export current state to JSON files for Obsidian/human review."""
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    count = 0
    for row in list_state():
        name = f"{row['namespace']}__{row['key']}.json".replace("/", "_")
        (target / name).write_text(
            json.dumps(row["payload"], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        count += 1
    return {"ok": True, "exported": count, "path": str(target)}


def health() -> dict[str, Any]:
    with session() as s:
        s.execute(text("SELECT 1"))
    return {"ok": True, "url": os.getenv("CLOUD_OS_DATABASE_URL") or str(DEFAULT_DB_PATH)}
