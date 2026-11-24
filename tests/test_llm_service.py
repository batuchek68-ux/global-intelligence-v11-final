from __future__ import annotations

import pytest

from backend.services.llm_service import enhance_brief, is_available, llm_enabled, summarize


def test_llm_disabled_by_default(monkeypatch):
    monkeypatch.delenv("OPS_USE_LLM", raising=False)
    assert llm_enabled() is False
    assert is_available() is False


def test_brief_falls_back_to_rules(monkeypatch):
    monkeypatch.setenv("OPS_USE_LLM", "0")
    content, source = enhance_brief("original brief", "Kazakhstan")
    assert source == "rules"
    assert content == "original brief"


def test_summary_falls_back_to_rules(monkeypatch):
    monkeypatch.setenv("OPS_USE_LLM", "0")
    out, source = summarize("text", "fallback")
    assert source == "rules"
    assert out == "fallback"


def test_brief_reports_source_when_disabled(monkeypatch):
    monkeypatch.setenv("OPS_USE_LLM", "0")
    _, source = enhance_brief("x", "y")
    assert source in {"rules", "llm+rules"}
