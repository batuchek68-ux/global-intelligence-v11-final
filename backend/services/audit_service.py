from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG = BACKEND_ROOT / "memory" / "audit.log"

_HASH_RE = re.compile(r" \| hash=([0-9a-f]{64})\s*$")
_GENESIS = "GENESIS"


def _line_hash(previous: str, line: str) -> str:
    return hashlib.sha256(f"{previous}|{line}".encode("utf-8")).hexdigest()


def _last_hash(target: Path) -> str:
    if not target.exists():
        return _GENESIS
    last = _GENESIS
    try:
        for raw in target.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _HASH_RE.search(raw)
            if m:
                last = m.group(1)
    except OSError:
        pass
    return last


def append_audit(
    action: str,
    result: str,
    note: str,
    *,
    role: str = "Codex",
    confidence: int = 90,
    risk: str = "LOW",
    path: Path | None = None,
) -> Path:
    """Append one hash-chained audit line; never rewrite historical evidence."""
    target = path or AUDIT_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    safe_note = " ".join(str(note).splitlines())
    base = f"{timestamp} | {role} | {action} | {confidence} | {risk} | {result} | {safe_note}"
    previous = _last_hash(target)
    chain_hash = _line_hash(previous, base)
    with target.open("a", encoding="utf-8", newline="") as handle:
        handle.write(f"{base} | hash={chain_hash}\n")
    return target


def verify_append_only_marker(path: Path | None = None) -> dict:
    target = path or AUDIT_LOG
    if not target.exists():
        return {"ok": True, "exists": False, "path": str(target)}
    text = target.read_text(encoding="utf-8", errors="replace")
    suspicious = ["TRUNCATE_AUDIT", "REWRITE_AUDIT", "DELETE_AUDIT"]
    return {
        "ok": not any(marker in text for marker in suspicious),
        "exists": True,
        "path": str(target),
        "lines": len([line for line in text.splitlines() if line.strip()]),
    }


def verify_audit_chain(path: Path | None = None) -> dict:
    """Verify every chained line and its order. Legacy unchained lines are reported."""
    target = path or AUDIT_LOG
    if not target.exists():
        return {"ok": True, "exists": False, "lines": 0, "chained": 0, "legacy": 0, "broken_at": None}
    previous = _GENESIS
    chained = legacy = 0
    broken_at = None
    for index, raw in enumerate(target.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not raw.strip():
            continue
        m = _HASH_RE.search(raw)
        if not m:
            legacy += 1
            continue
        base = raw[: m.start()].rstrip()
        claimed = m.group(1)
        if _line_hash(previous, base) != claimed:
            broken_at = index
            break
        previous = claimed
        chained += 1
    return {
        "ok": broken_at is None,
        "exists": True,
        "lines": chained + legacy,
        "chained": chained,
        "legacy": legacy,
        "broken_at": broken_at,
    }
