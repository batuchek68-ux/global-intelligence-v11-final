"""Local-knowledge RAG augmentation for intelligence briefs.

Offline-safe and deterministic: retrieval comes only from the local
knowledge_ingest_service index, and no network calls are made here.
"""
from __future__ import annotations

from backend.services import knowledge_ingest_service
from backend.services.knowledge_ingest_service import query  # re-exported public API


def augment_brief(content: str, focus: str, n: int = 5) -> tuple[str, str]:
    """Append retrieved local-knowledge evidence to ``content``.

    Returns ``(content, source)`` where ``source`` is ``"rag"`` when at least
    one chunk was appended, otherwise ``"rules"`` (including on any failure).
    """
    try:
        result = knowledge_ingest_service.query(focus, n=n)
    except Exception:
        return content, "rules"

    if not isinstance(result, dict) or not result.get("ok"):
        return content, "rules"

    rows = result.get("results") or []
    chunks = [row for row in rows if isinstance(row, dict) and row.get("text")]
    if not chunks:
        return content, "rules"

    lines = ["", "## Local Knowledge Evidence", ""]
    for row in chunks[:n]:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        source = meta.get("source", "unknown")
        title = meta.get("title", "untitled")
        path = meta.get("path", "")
        lines.append(f"- Source: {source} | Title: {title} | Path: {path}")
        lines.append("")
        lines.append(str(row["text"]))
        lines.append("")

    new_content = content.rstrip("\n") + "\n" + "\n".join(lines).rstrip("\n") + "\n"
    return new_content, "rag"
