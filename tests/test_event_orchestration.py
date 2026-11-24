from __future__ import annotations

from backend.services import realtime_source_service as rss
from backend.services import event_bus
from backend.workflows import event_orchestrator


def test_poll_sources_publishes_events(monkeypatch):
    calls = []
    monkeypatch.setattr(rss, "fetch_rss", lambda url: [{"title": "News", "link": "http://x", "published": "now"}])
    monkeypatch.setattr(event_bus, "publish", lambda t, p: calls.append((t, p)) or {"id": "x", "type": t})
    result = rss.poll_sources([{"name": "demo", "url": "http://x/rss"}])
    assert result["ok"] is True
    assert result["published"] == 1
    assert calls[0][0] == "intel.source_updated"
    assert calls[0][1]["source"] == "demo"


def test_orchestrator_runs_cycle_and_emits_events(monkeypatch):
    events = []
    monkeypatch.setattr(event_bus, "publish", lambda t, p: events.append((t, p)) or {"id": "e1", "type": t})
    monkeypatch.setattr(
        "backend.workflows.daily_job.run_daily_cycle",
        lambda: {"project_count": 2, "case_count": 2, "major_matter_count": 1},
    )
    monkeypatch.setenv("CLOUD_OS_EVENT_TYPE", "intel.source_updated")
    result = event_orchestrator.run()
    assert result["ok"] is True
    assert [t for t, _ in events] == ["intel.source_updated", "daily_cycle.completed"]
    assert events[1][1]["project_count"] == 2
