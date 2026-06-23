from __future__ import annotations

from datetime import datetime
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG = BACKEND_ROOT / "memory" / "audit.log"


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
    """Append one immutable audit line; never rewrite historical evidence."""
    target = path or AUDIT_LOG
    target.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    safe_note = " ".join(str(note).splitlines())
    line = f"{timestamp} | {role} | {action} | {confidence} | {risk} | {result} | {safe_note}\n"
    with target.open("a", encoding="utf-8", newline="") as handle:
        handle.write(line)
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
