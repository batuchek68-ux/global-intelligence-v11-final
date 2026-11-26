# -*- coding: utf-8 -*-
"""Fetch a Russian/Kazakh webpage and save readable text + provenance.

Practical ru/kk source collector for the base information layer.
No login, no paywall bypass, no CAPTCHA solving — public pages only.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

OUT_ROOT = Path("F:/Documents/Obsidian Vault/obsidian-codex/00-输入池/研究简报/俄语源抓取")


def slug(url: str) -> str:
    s = re.sub(r"^https?://", "", url)
    s = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", s)[:80]
    return s.strip("_") or "page"


def save(url: str, text: str, lang: str = "ru") -> Path:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    target = OUT_ROOT / (datetime.now().strftime("%Y%m%d") + "_" + slug(url) + ".md")
    header = (
        "---\n"
        "title: 俄语源抓取 · " + slug(url) + "\n"
        "tags:\n  - 俄语源\n  - 哈萨克斯坦\n  - 抓取\n"
        "generated: " + datetime.now(timezone.utc).strftime("%Y-%m-%d") + "\n"
        "source_url: " + url + "\n"
        "source_lang: " + lang + "\n"
        "method: 公开页直抓，无登录/无付费墙绕过\n"
        "---\n\n"
    )
    target.write_text(header + "# " + url + "\n\n" + text[:60000], encoding="utf-8")
    return target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="public ru/kk page URL")
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--text", help="already-fetched text (optional; else print instructions)")
    a = ap.parse_args()
    if a.text:
        p = save(a.url, a.text, a.lang)
        print(json.dumps({"ok": True, "path": str(p), "chars": len(a.text)}, ensure_ascii=False))
    else:
        # Actual fetching is done by webfetch (Code Mode / agent). This CLI is the
        # storage contract so every fetched page is archived with provenance.
        print(json.dumps({
            "ok": False,
            "hint": "fetch the URL with webfetch(format:text), then call: python fetch_ru_page.py URL --lang ru --text '<text>'",
            "url": a.url,
        }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
