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
        {"id": "kazakhstan_customs", "query": "Kazakhstan customs clearance documents EAEU", "expect": ["customs", "哈萨克斯坦", "海关"], "source": "wiki"},
        {"id": "port_payment", "query": "port project payment terms guarantee negotiation", "expect": ["payment", "guarantee", "付款"], "source": "wechat_favorites"},
        {"id": "sanctions_risk", "query": "sanctions export control risk government approval", "expect": ["风控", "风险", "risk", "审批", "approval", "制裁"], "source": "ima"},
        {"id": "agent_workflow", "query": "Codex ACP Zed local AI workflow", "expect": ["codex", "workflow", "agent"], "source": "wiki"},
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


def _citation_ok(items: list[dict[str, Any]], case: dict[str, Any]) -> bool:
    """引证可定位：结果须有 source/path；若金标准指定 sources 则须命中其一。"""
    if not case.get("citation") and not case.get("sources"):
        return True
    top = items[:3]
    if not top:
        return False
    sources = [str((i.get("metadata") or {}).get("source") or "") for i in top]
    paths = [str((i.get("metadata") or {}).get("path") or "") for i in top]
    expected = case.get("sources")
    if expected:
        return bool(set(sources) & {str(s) for s in expected})
    return any(sources) and any(paths)


def evaluate(n: int = 5) -> dict[str, Any]:
    cases = load_gold_set()
    stats = knowledge.stats()
    results = []
    hits = 0
    citation_hits = 0
    for case in cases:
        query = str(case.get("query") or "")
        response = hybrid_query(query, n=n)
        items = response.get("results", []) if response.get("ok") else []
        blob = " ".join(str(i.get("text") or "") for i in items).lower()
        expect = [str(e).lower() for e in case.get("expect", [])]
        found = [e for e in expect if e in blob]
        core = [str(e).lower() for e in case.get("core", [])]
        if core:
            # 同义词表长度不应决定阈值：命中 2 个同义词，或命中任一核心术语，即判相关。
            keyword_ok = len(found) >= 2 or bool(set(core) & set(found))
        else:
            keyword_ok = bool(expect) and len(found) >= max(1, len(expect) // 2)
        cited = _citation_ok(items, case)
        ok = keyword_ok and cited
        hits += int(ok)
        citation_hits += int(cited)
        results.append({
            "id": case.get("id"),
            "domain": case.get("domain"),
            "query": query,
            "expected": expect,
            "found": found,
            "keyword_ok": keyword_ok,
            "citation_ok": cited,
            "ok": ok,
            "top_sources": [(i.get("metadata") or {}).get("source") for i in items[:3]],
        })
    accuracy = (hits / len(cases)) if cases else 0.0
    citation_accuracy = (citation_hits / len(cases)) if cases else 0.0
    report = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "index": stats,
        "total": len(cases),
        "hits": hits,
        "accuracy": round(accuracy, 4),
        "citation_hits": citation_hits,
        "citation_accuracy": round(citation_accuracy, 4),
        "results": results,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = REPORT_DIR / "rag_quality.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    append_audit("RAG_BENCHMARK", "DONE", f"accuracy={report['accuracy']} hits={hits}/{len(cases)}", confidence=int(accuracy * 100), risk="LOW")
    return report
