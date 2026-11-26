# -*- coding: utf-8 -*-
"""Build a unified MOC index for scattered reports. Read-only: never moves notes."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VAULT = Path("F:/Documents/Obsidian Vault")
OUT = VAULT / "obsidian-codex" / "00-输入池" / "研究简报" / "_MOC.md"

SECTIONS = [
    ("研究简报", VAULT / "obsidian-codex" / "00-输入池" / "研究简报"),
    ("系统自动化", VAULT / "obsidian-codex" / "05-系统自动化"),
]
EXCLUDE = {"_MOC.md", "_索引.md", "_skill_catalog.md", "每日处理清单.md"}


def parse_frontmatter(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not text.startswith("---\n"):
        return out
    end = text.find("\n---\n", 4)
    if end < 0:
        return out
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().strip("-").strip()
        value = value.strip().strip('"').strip("'")
        if key in ("title", "generated", "source"):
            out[key] = value
        elif key == "tags":
            out["tags"] = [t.strip().strip("-") for t in value.replace("[", "").replace("]", "").split(",") if t.strip()]
    return out


def summarize(text: str, limit: int = 110) -> str:
    # drop frontmatter
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            text = text[end + 5:]
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(">") or s.startswith("|") or s.startswith("- "):
            continue
        s = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", r"\2\1", s)
        s = re.sub(r"[*`_]", "", s)
        if len(s) > 12:
            lines.append(s)
        if len(" ".join(lines)) >= limit:
            break
    summary = " ".join(lines)
    return summary[:limit] + ("…" if len(summary) > limit else "")


def main() -> dict[str, Any]:
    sections: list[tuple[str, list[dict[str, Any]]]] = []
    total = 0
    for label, root in SECTIONS:
        items = []
        if root.is_dir():
            for path in sorted(root.glob("*.md")):
                if path.name in EXCLUDE:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                fm = parse_frontmatter(text)
                rel = path.relative_to(VAULT).as_posix()
                items.append({
                    "rel": rel,
                    "title": fm.get("title") or path.stem,
                    "tags": fm.get("tags") or [],
                    "date": fm.get("generated") or "",
                    "summary": summarize(text),
                })
        total += len(items)
        sections.append((label, items))

    lines = [
        "---",
        "title: 报告统一索引（MOC）",
        "tags:",
        "  - moc",
        "  - 索引",
        "generated: " + datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "---",
        "",
        "# 报告统一索引（MOC）",
        "",
        "> 自动生成的报告入口页。**所有文件保留在原位**，本页只做索引，不移动、不改写原文档。",
        "> 新报告通过桌面控制台导出到 `00-输入池/研究简报/` 后会自动纳入本索引。",
        "",
    ]
    for label, items in sections:
        lines.append("## %s（%d）" % (label, len(items)))
        lines.append("")
        if not items:
            lines.append("_暂无_")
            lines.append("")
            continue
        for item in items:
            lines.append("- [[%s|%s]]" % (item["rel"], item["title"]))
            meta = []
            if item["date"]:
                meta.append(item["date"])
            meta += ["#" + t for t in item["tags"][:5]]
            if meta:
                lines.append("  - " + " · ".join(meta))
            if item["summary"]:
                lines.append("  - " + item["summary"])
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"ok": True, "path": str(OUT), "total": total, "sections": {k: len(v) for k, v in sections}}


if __name__ == "__main__":
    result = main()
    print("MOC_OK total=%d path=%s sections=%s" % (result["total"], result["path"], result["sections"]))
