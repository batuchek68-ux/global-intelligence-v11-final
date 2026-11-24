"""Opt-in LLM enhancement with deterministic fallback.

v12 keeps all intelligence outputs reproducible in CI by default. Setting
OPS_USE_LLM=1 enables a local/compatible OpenAI-style endpoint (FreeLLMAPI by
default). Any failure degrades silently to the rule/template output.
"""
from __future__ import annotations

import json
import os
from typing import Any

import requests


def llm_enabled() -> bool:
    return os.getenv("OPS_USE_LLM", "0") == "1"


def _endpoint() -> str:
    return (os.getenv("FREELLMAPI_BASE_URL") or "http://127.0.0.1:31415/v1").rstrip("/")


def _headers() -> dict[str, str]:
    key = os.getenv("FREELLMAPI_KEY") or ""
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _model() -> str:
    return os.getenv("FREELLMAPI_MODEL") or "auto"


def is_available(timeout: float = 5) -> bool:
    if not llm_enabled():
        return False
    try:
        r = requests.get(f"{_endpoint()}/models", headers=_headers(), timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def chat(messages: list[dict[str, str]], max_tokens: int = 600, temperature: float = 0.4) -> str:
    payload = {"model": _model(), "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    r = requests.post(f"{_endpoint()}/chat/completions", json=payload, headers=_headers(), timeout=60)
    r.raise_for_status()
    data = r.json()
    choices = data.get("choices") or []
    if not choices:
        return ""
    return str(choices[0].get("message", {}).get("content") or "")


def enhance_brief(content: str, focus: str, max_items: int = 12) -> tuple[str, str]:
    """Return (content, source). Falls back to the original content."""
    if not is_available():
        return content, "rules"
    try:
        excerpt = content[:4000]
        prompt = (
            f"You are an international engineering trade intelligence analyst.\n"
            f"Focus: {focus}\n\nRead the DRAFT brief below. Produce a concise analysis with:\n"
            "1) Key signals that matter for business decisions\n"
            "2) Risks requiring human verification\n"
            "3) 3 concrete follow-up research tasks\n"
            "Do not invent facts. Cite only what appears in the brief.\n\n"
            f"BRIEF:\n{excerpt}\n\nANALYSIS:"
        )
        out = chat(
            [{"role": "system", "content": "Respond in the language of the brief. Be precise and conservative."},
             {"role": "user", "content": prompt}],
            max_tokens=max_items * 60,
        ).strip()
        if not out:
            return content, "rules"
        return content + "\n## LLM Analysis\n\n" + out + "\n", "llm+rules"
    except Exception:
        return content, "rules"


def summarize(text: str, fallback: str) -> tuple[str, str]:
    if not is_available():
        return fallback, "rules"
    try:
        out = chat(
            [{"role": "system", "content": "Summarize concisely, keep key facts."},
             {"role": "user", "content": text[:3000]}],
            max_tokens=300,
            temperature=0.3,
        ).strip()
        return (out or fallback), ("llm" if out else "rules")
    except Exception:
        return fallback, "rules"
