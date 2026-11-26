# -*- coding: utf-8 -*-
"""Search Russian/Kazakh web via the in-app browser (Google), then extract result text.

This is the practical substitute for paid search APIs under zero budget:
Yandex triggers SmartCaptcha; Google browser channel works for ru/kk queries.
Used by data-collection agents to discover authoritative ru/kk sources.
"""
from __future__ import annotations

import json
import subprocess
import sys

# The browser is driven by OpenCode's browse/MCP extension, not a local binary.
# This script is the contract/interface; actual calls are made by the agent via
# tools.browser inside Code Mode. Here we expose a CLI that prints the query plan
# and expected source domains, so the agent can log and verify coverage.
DOMAINS_RU = [
    "gov.kz", "adilet.zan.kz", "stat.gov.kz", "nationalbank.kz",
    "aifc.kz", "kgd.gov.kz", "apk-news.kz", "grainunion.kz",
    "kursiv.media", "ranking.kz", "energyprom.kz", "zakon.kz",
    "eec.eaeunion.org", "uchet.kz", "mybuh.kz", "pro1c.kz", "finance.kz",
    "exl.kz", "alternadv.com", "calculators.kz", "tnved.info",
]
DOMAINS_KK = [
    "gov.kz", "adilet.zan.kz", "stat.gov.kz", "kisi.kz",
    "primeminister.kz", "akorda.kz",
]


def plan(query: str, lang: str = "ru") -> dict:
    goog = "https://www.google.com/search?q=" + query.replace(" ", "+") + "&hl=" + lang
    return {
        "query": query,
        "lang": lang,
        "search_url": goog,
        "expected_domains": DOMAINS_KK if lang == "kk" else DOMAINS_RU,
        "captcha_fallback": "Yandex blocked by SmartCaptcha; use Google browser channel",
        "note": "Search discovers URLs; then use webfetch(format:text) on each result URL for full text.",
    }


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "ставка НДС Казахстан 2026"
    lang = sys.argv[2] if len(sys.argv) > 2 else "ru"
    print(json.dumps(plan(q, lang), ensure_ascii=False, indent=2))
