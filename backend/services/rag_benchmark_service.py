"""Measure retrieval quality against a local gold-set.

The gold-set is versioned in the repo; reports are written under reports/benchmark.
No model training or network access is involved.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services import knowledge_ingest_service as knowledge
from backend.services.hybrid_retrieval_service import hybrid_query
from backend.services.audit_service import append_audit

BACKEND_ROOT = Path(__file__).resolve().parents[1]
GOLD_SET = BACKEND_ROOT / ".." / "tests" / "data" / "rag_gold_set.json"
REPORT_DIR = BACKEND_ROOT / "reports" / "benchmark"


def default_gold_set() -> list[dict[str, Any]]:
    return [
        {"id": "kazakhstan_customs", "query": "Kazakhstan customs clearance documents EAEU", "expect": ["customs"], "source": "wiki"},
        {"id": "port_payment", "query": "port project payment terms guarantee negotiation", "expect": ["payment", "guarantee"], "source": "wechat_favorites"},
        {"id": "sanctions_risk", "query": "sanctions export control risk government approval", "expect": ["sanction", "approval"], "source": "ima"},
        {"id": "agent_workflow", "query": "Codex ACP Zed local AI workflow", "expect": ["codex", "workflow"], "source": "wiki"},
        {"id": "trade_report", "query": "哈萨克斯坦 矿冶 机械设备 市场", "expect": ["哈萨克斯坦", "矿冶"], "source": "ima"},
    ]


def load_gold_set() -> list[dict[str, Any]]:
    path = GOLD_SET.resolve()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return default_gold_set()


def evaluate(n: int = 5) -> dict[str, Any]:
    cases = load_gold_set()
    stats = knowledge.stats()
    results = []
    hits = 0
    for case in cases:
        query = str(case.get("query") or "")
        response = hybrid_query(query, n=n)
        items = response.get("results", []) if response.get("ok") else []
        blob = " ".join(str(i.get("text") or "") for i in items).lower()
        expect = [str(e).lower() for e in case.get("expect", [])]
        found = [e for e in expect if e in blob]
        ok = bool(expect) and len(found) >= max(1, len(expect) // 2)
        hits += int(ok)
        results.append({
            "id": case.get("id"),
            "query": query,
            "expected": expect,
            "found": found,
            "ok": ok,
            "top_sources": [i.get("metadata", {}).get("source") for i in items[:3]],
        })
    accuracy = (hits / len(cases)) if cases else 0.0
    report = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "index": stats,
        "total": len(cases),
        "hits": hits,
        "accuracy": round(accuracy, 4),
        "results": results,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = REPORT_DIR / "rag_quality.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    append_audit("RAG_BENCHMARK", "DONE", f"accuracy={report['accuracy']} hits={hits}/{len(cases)}", confidence=int(accuracy * 100), risk="LOW")
    return report
