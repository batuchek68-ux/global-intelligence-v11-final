from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def ensure_dirs() -> None:
    for path in [
        ROOT / "memory" / "cases",
        ROOT / "memory" / "continuations",
        ROOT / "memory" / "decisions",
        ROOT / "memory" / "execution_logs",
        ROOT / "memory" / "operator_logs",
        ROOT / "research" / "briefs",
        ROOT / "media" / "drafts",
        ROOT / "reports",
        ROOT / "reports" / "business_flows",
        ROOT / "comm" / "outbox",
        ROOT / "projects" / "active",
        ROOT / "projects" / "templates",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def safe_slug(text: str) -> str:
    allowed = []
    for char in text.lower():
        if char.isalnum():
            allowed.append(char)
        elif char in (" ", "-", "_"):
            allowed.append("-")
    slug = "".join(allowed).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "project"
