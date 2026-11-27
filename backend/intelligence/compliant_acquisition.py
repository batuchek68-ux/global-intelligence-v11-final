"""把合规采集结果接入 v11 五任务 DAG 的适配器。

现有链路（backend/core/orchestration.py）：
  task_1 classifier -> task_2 extractor -> task_3 evidence_planner
  -> task_4 risk_gate -> task_5 synthesizer

EvidencePlannerAgent 目前只产出 search_queries 字符串，从不执行。
本适配器让 collector agent 真正执行这些查询，并把 provenance 交给 Judge。

用法：在 OrchestrationEngine.register_agent 注册 CompliantCollectorAgent("collector")，
并在 _build_task_graph 中插入 task_3b（依赖 task_3），task_4 依赖改为 task_3b。
"""
from __future__ import annotations

import asyncio
from typing import Any

try:  # 落地后 src/fetch_news.py 是替换后的文件名
    from src.fetch_news import build_resolver, _load_config
except ModuleNotFoundError:  # 源包内仍叫 fetch_news_integrated.py
    from src.fetch_news_integrated import build_resolver, _load_config


class CompliantCollectorAgent:
    """可作为 agent_type="collector" 注册进 AgentPool。"""

    def __init__(self, config_path: str | None = None):
        self.name = "collector"
        self.config = _load_config() if config_path is None else _load_config(__import__("pathlib").Path(config_path))
        self.metrics = {"executions": 0, "errors": 0, "items": 0}

    async def execute_async(self, input_data: dict[str, Any], org_id: str) -> dict[str, Any]:
        evidence = input_data.get("prev_task_3", {}) or {}
        queries: list[str] = evidence.get("search_queries") or []
        if not queries:
            queries = [str(input_data.get("query") or "")]
        resolver = build_resolver(self.config)
        collected: list[dict[str, Any]] = []
        seen_urls: set[str] = set()                  # 跨 query 去重（resolver 只管单次）
        for q in queries[:6]:                       # 最多 6 条，避免打爆配额
            try:
                # resolve 内含限流 sleep，放到线程里避免阻塞 FastAPI 事件循环
                items = await asyncio.to_thread(
                    resolver.resolve, q,
                    self.config.get("gdelt", {}).get("default_timespan", "24h"),
                )
            except Exception:
                self.metrics["errors"] += 1
                continue
            for e in items:
                if e.item.url in seen_urls:
                    continue
                seen_urls.add(e.item.url)
                collected.append(e.to_dict())
        # deny/unreachable 的条目已被 resolver 丢弃，只能从降级日志统计
        robots_denied = sum(
            1 for f in resolver.fallback_log
            if f.get("reason", "").startswith("robots:")
        )
        self.metrics["executions"] += 1
        self.metrics["items"] += len(collected)
        return {
            "status": "collection_ready",
            "items": collected,
            "item_count": len(collected),
            "robots_denied": robots_denied,
            "fallback_log": resolver.fallback_log,
            "required_sources": evidence.get("required_sources", []),
            "audit_hint": "Provenance attached; Judge must reject items without source_tier/robots_decision/fetched_at.",
        }


def validate_provenance(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """供 Judge / evidence_verification_service 调用的入库前硬校验。"""
    required = {"source_tier", "fetch_url", "robots_decision", "fetched_at"}
    accepted: list[dict[str, Any]] = []
    rejected: list[str] = []
    for rec in records:
        prov = rec.get("provenance") or rec.get("_provenance") or {}
        missing = required - set(prov)
        if missing:
            rejected.append(f"{rec.get('url', '?')}: missing {sorted(missing)}")
            continue
        if prov.get("robots_decision") in ("deny", "unreachable"):
            rejected.append(f"{rec.get('url', '?')}: robots={prov['robots_decision']}")
            continue
        accepted.append(rec)
    return accepted, rejected
