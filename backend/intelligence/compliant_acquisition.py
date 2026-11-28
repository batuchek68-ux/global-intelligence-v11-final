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
from concurrent.futures import ThreadPoolExecutor
from typing import Any

try:  # 落地后 src/fetch_news.py 是替换后的文件名
    from src.fetch_news import build_resolver, _load_config
except ModuleNotFoundError:  # 源包内仍叫 fetch_news_integrated.py
    from src.fetch_news_integrated import build_resolver, _load_config


class CompliantCollectorAgent:
    """可作为 agent_type="collector" 注册进 AgentPool。

    查询预算（条数 / 并发度 / 单查询超时）来自 config/sources.json 的
    collection 段，避免默认 6 条串行 + GDELT 长退避把 /v1/query 拖到超时。
    """

    DEFAULT_MAX_QUERIES = 6
    DEFAULT_MAX_CONCURRENCY = 3
    DEFAULT_QUERY_TIMEOUT = 20.0

    def __init__(self, config_path: str | None = None):
        self.name = "collector"
        self.config = _load_config() if config_path is None else _load_config(__import__("pathlib").Path(config_path))
        self.metrics = {"executions": 0, "errors": 0, "items": 0}
        budget = self.config.get("collection", {})
        self.budget = budget
        self.max_queries = max(1, int(budget.get("max_queries", self.DEFAULT_MAX_QUERIES)))
        self.max_concurrency = max(1, int(budget.get("max_concurrency", self.DEFAULT_MAX_CONCURRENCY)))
        self.query_timeout = max(0.1, float(budget.get("query_timeout_seconds", self.DEFAULT_QUERY_TIMEOUT)))

    async def execute_async(self, input_data: dict[str, Any], org_id: str) -> dict[str, Any]:
        del org_id
        evidence = input_data.get("prev_task_3", {}) or {}
        queries: list[str] = evidence.get("search_queries") or []
        if not queries:
            queries = [str(input_data.get("query") or "")]
        queries = queries[:self.max_queries]
        gdelt_cfg = self.config.get("gdelt", {})
        timespan = gdelt_cfg.get("default_timespan", "24h")
        language = gdelt_cfg.get("default_language", "english")
        # planner 产出的 rss_query 是短查询；RSS 层只做关键词匹配，用它而非长模板。
        # 老 planner 没有该字段时退化为逐条 query（RSS token 匹配仍能处理）。
        rss_query = str(evidence.get("rss_query") or "").strip()
        # 真实环境只有 planner 的短查询有召回（长模板查询在 RSS 上是零命中）。
        # short_query_only 下只跑这一条，把预算留给单查询的完整降级链。
        if rss_query and self.budget.get("short_query_only", False):
            queries = [rss_query]
        # API 路径对 GDELT 用更激进的重试上限：被限流时快速降级到 RSS，
        # 避免 2 次退避 + 每次超时吃满单查询预算。fetch_news 独立运行仍用 config 默认值。
        api_retries = self.budget.get("api_retries")
        if api_retries is not None:
            self.config = {**self.config, "gdelt": {
                **self.config.get("gdelt", {}), "max_retries": api_retries,
            }}
        resolver = build_resolver(self.config)
        seen_lock = asyncio.Lock()
        seen_urls: set[str] = set()                  # 跨 query 去重（resolver 只管单次）

        # 并发上限必须落在「真正干活的线程」上。asyncio.Semaphore 只约束协程，
        # wait_for 超时后槽位会释放但底层线程仍在跑，实际并发会突破上限。
        # 有界 ThreadPoolExecutor 保证同时运行的 resolver.resolve 不超过 max_concurrency。
        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(
            max_workers=self.max_concurrency,
            thread_name_prefix="gi-collector",
        )

        async def collect_one(query: str) -> list[dict[str, Any]]:
            # wait_for 只缩短 API 等待；底层线程受 executor 有界约束，不会拖垮配额。
            try:
                items = await asyncio.wait_for(
                    loop.run_in_executor(
                        executor, resolver.resolve, query, timespan, language,
                        rss_query or query,
                    ),
                    timeout=self.query_timeout,
                )
            except Exception:
                self.metrics["errors"] += 1
                return []
            out: list[dict[str, Any]] = []
            for e in items:
                async with seen_lock:
                    if e.item.url in seen_urls:
                        continue
                    seen_urls.add(e.item.url)
                out.append(e.to_dict())
            return out

        try:
            batches = await asyncio.gather(*(collect_one(q) for q in queries))
        finally:
            # 不等待超时后仍在跑的线程，避免 API 结束前被反向拖住。
            executor.shutdown(wait=False, cancel_futures=True)
        collected = [item for batch in batches for item in batch]
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
            "collection_budget": {
                "max_queries": self.max_queries,
                "max_concurrency": self.max_concurrency,
                "query_timeout_seconds": self.query_timeout,
            },
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
