from __future__ import annotations

import re
from pathlib import Path


V12 = Path("F:/Documents/GitHub/global-intelligence-v11-final/.github/workflows")
LEGACY = Path("F:/Documents/GitHub/global-intelligence-system/.github/workflows")


def active_crons(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    in_on = False
    result = []
    for line in lines:
        if re.match(r"^on:\s*$", line):
            in_on = True
            continue
        if in_on and re.match(r"^[a-zA-Z_]+:\s*$", line) and not line.startswith("  "):
            in_on = False
        if in_on:
            m = re.search(r"cron:\s*[\"']([^\"']+)", line)
            if m:
                result.append(m.group(1))
    return result


def test_event_orchestrator_is_the_only_timer_in_v12():
    assert active_crons(V12 / "event_orchestrator.yml") == ["0 */6 * * *"]
    assert active_crons(V12 / "ai.yml") == []
    assert active_crons(V12 / "watchdog.yml") == []


def test_legacy_schedules_retired():
    for name in ("daily.yml", "global-intelligence-v3.yml", "intelligence.yml", "watchdog.yml"):
        path = LEGACY / name
        if path.exists():
            assert active_crons(path) == [], f"{name} still has an active cron"
