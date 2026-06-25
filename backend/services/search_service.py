from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote_plus


TRADE_EXPANSIONS = [
    "EPC",
    "engineering procurement construction",
    "public tender",
    "government project",
    "investment project",
    "feasibility study",
    "EIA public hearing",
    "project owner",
    "developer investor",
    "responsible person contact",
    "mining infrastructure",
    "port logistics",
    "customs clearance",
    "HS code tariff",
    "certificate of origin",
    "payment risk",
    "sanctions compliance",
    "export control",
    "local contractor",
]

REGIONAL_TERMS = {
    "kazakhstan": ["Kazakhstan", "Qazaqstan", "Казахстан", "哈萨克斯坦"],
    "central_asia": ["Central Asia", "Центральная Азия", "中亚"],
    "uzbekistan": ["Uzbekistan", "Узбекистан", "乌兹别克斯坦"],
    "kyrgyzstan": ["Kyrgyzstan", "Кыргызстан", "吉尔吉斯斯坦"],
}

OFFICIAL_SEARCH_DOMAINS = {
    "kazakhstan": ["gov.kz", "primeminister.kz", "invest.gov.kz", "adilet.zan.kz", "goszakup.gov.kz", "sk.kz"],
    "central_asia": ["gov.kz", "gov.uz", "gov.kg", "tajinvest.tj", "gov.tm"],
    "uzbekistan": ["gov.uz", "invest.gov.uz", "lex.uz", "xarid.uzex.uz"],
    "kyrgyzstan": ["gov.kg", "mineconom.gov.kg", "zakupki.gov.kg"],
}

INTELLIGENCE_CATEGORIES = [
    {
        "id": "government_confirmation",
        "label": "政府官网确认",
        "required": True,
        "terms": ["official government", "ministry", "akimat", "cabinet", "project page"],
        "reason": "先确认项目是否真实存在、主管部门是谁、处于计划建设还是在建阶段。",
    },
    {
        "id": "procurement_tender",
        "label": "招标采购",
        "required": True,
        "terms": ["public tender", "procurement", "EPC tender", "contract awarded", "bid notice"],
        "reason": "判断采购阶段、总包/分包机会、招标变化和可参与窗口。",
    },
    {
        "id": "customs_trade",
        "label": "海关与贸易合规",
        "required": True,
        "terms": ["customs", "HS code", "tariff", "certificate of origin", "import license", "export control"],
        "reason": "核验关税、清关文件、出口管制、制裁和付款交付风险。",
    },
    {
        "id": "stakeholders",
        "label": "项目负责人和开发者",
        "required": False,
        "terms": ["project owner", "developer", "investor", "responsible person", "contact"],
        "reason": "建立招商引资和项目推进联系人图谱。",
    },
    {
        "id": "research_feasibility",
        "label": "科研与可行性",
        "required": False,
        "terms": ["feasibility study", "EIA", "technical report", "paper", "standard", "library"],
        "reason": "把论文、标准、图书馆资料转成可行性报告证据。",
    },
    {
        "id": "public_attention",
        "label": "论坛社媒和视频关注度",
        "required": False,
        "terms": ["YouTube", "TikTok", "Douyin", "Telegram", "forum", "public sentiment"],
        "reason": "只作为关注度和传播选题信号，不能替代官方证据。",
    },
]


def _region_key(query: str) -> str:
    lower = query.lower()
    if any(term in lower for term in ["uzbekistan", "乌兹别克斯坦", "узбекистан"]):
        return "uzbekistan"
    if any(term in lower for term in ["kyrgyzstan", "吉尔吉斯斯坦", "кыргызстан"]):
        return "kyrgyzstan"
    if any(term in lower for term in ["kazakhstan", "qazaqstan", "哈萨克斯坦", "казахстан"]):
        return "kazakhstan"
    return "central_asia"


def enrich_query(query: str) -> dict[str, Any]:
    normalized = query.strip()
    region_key = _region_key(normalized)
    regions = REGIONAL_TERMS[region_key]
    enriched: list[str] = []
    for region in regions:
        for term in TRADE_EXPANSIONS:
            enriched.append(f"{normalized} {region} {term}")

    category_queries = [
        {
            "category": category["id"],
            "label": category["label"],
            "required": category["required"],
            "queries": [f"{normalized} {regions[0]} {term}" for term in category["terms"]],
            "reason": category["reason"],
        }
        for category in INTELLIGENCE_CATEGORIES
    ]
    return {
        "original": normalized,
        "region_key": region_key,
        "regions": regions,
        "trade_terms": TRADE_EXPANSIONS,
        "queries": enriched[:36],
        "category_queries": category_queries,
    }


def _manual_search(name: str, base_url: str, query: str, *, source_type: str = "search_entry") -> dict[str, Any]:
    return {
        "source": name,
        "status": "manual_search_url",
        "source_type": source_type,
        "results": [],
        "url": f"{base_url}{quote_plus(query)}",
        "query": query,
    }


def _project_search_queries(query: str) -> list[dict[str, Any]]:
    enriched = enrich_query(query)
    domains = OFFICIAL_SEARCH_DOMAINS[enriched["region_key"]]
    plans: list[dict[str, Any]] = []
    for category in enriched["category_queries"]:
        for candidate in category["queries"][:3]:
            if category["required"]:
                for domain in domains[:4]:
                    plans.append(
                        {
                            "intent": category["category"],
                            "label": category["label"],
                            "query": f"{candidate} site:{domain}",
                            "required": True,
                            "evidence_tier": "official",
                            "reason": category["reason"],
                        }
                    )
            else:
                plans.append(
                    {
                        "intent": category["category"],
                        "label": category["label"],
                        "query": candidate,
                        "required": False,
                        "evidence_tier": "supporting",
                        "reason": category["reason"],
                    }
                )
    return plans[:72]


def build_source_readiness(sources: list[dict[str, Any]]) -> dict[str, Any]:
    configured = [source for source in sources if source.get("status") in {"configured", "manual_search_url"}]
    missing = [source for source in sources if source.get("status") == "missing_configuration"]
    live_ready = [source for source in sources if source.get("status") == "configured"]
    manual = [source for source in sources if source.get("status") == "manual_search_url"]
    return {
        "ok": not missing,
        "configured_count": len(configured),
        "live_adapter_count": len(live_ready),
        "manual_entry_count": len(manual),
        "missing_configuration": [{"source": item["source"], "reason": item.get("reason", "")} for item in missing],
        "explanation": (
            "Live API keys improve automation, but manual official search URLs are still provided. "
            "A source being reachable does not confirm a project; evidence must be attached and verified."
        ),
    }


def build_project_confirmation_gate(project_queries: list[dict[str, Any]], attached_evidence_count: int = 0) -> dict[str, Any]:
    required_intents = ["government_confirmation", "procurement_tender", "customs_trade"]
    required_queries = {intent: [item for item in project_queries if item["intent"] == intent and item["required"]][:4] for intent in required_intents}
    return {
        "status": "lead_only" if attached_evidence_count == 0 else "evidence_review_required",
        "can_create_confirmed_project_record": False,
        "can_create_lead_record": True,
        "required_before_confirmed_project": [
            "政府官网或官方采购页面确认项目存在、阶段、主管部门。",
            "海关或官方税则资料确认 HS code、关税、进口许可、清关文件。",
            "官方企业、政府或采购资料确认业主、开发者、投资方或负责人候选。",
            "证据进入 /v1/evidence/verify，置信度和风险边界通过后，再进入项目库确认。",
        ],
        "required_query_groups": required_queries,
        "blocked_until_confirmed": [
            "招商引资正式发布",
            "客户外联",
            "报价",
            "合同或付款承诺",
            "交期或清关承诺",
            "公开视频发布",
        ],
    }


def build_search_execution_brief(query: str, enriched: dict[str, Any], project_queries: list[dict[str, Any]]) -> dict[str, Any]:
    required = [item for item in project_queries if item["required"]]
    official = [item for item in required if item["intent"] == "government_confirmation"]
    customs = [item for item in required if item["intent"] == "customs_trade"]
    procurement = [item for item in required if item["intent"] == "procurement_tender"]
    confirmation_gate = build_project_confirmation_gate(project_queries)
    return {
        "mode": "search_to_execution_brief",
        "query": query,
        "region": enriched["region_key"],
        "verification_status": "search_plan_only",
        "confidence": 30,
        "why_not_confirmed": "No live official evidence item has been attached yet. Search results are leads, not confirmed facts.",
        "evidence_requirements": [
            "At least one official government or procurement page for project existence and stage.",
            "Customs authority, tariff database, or broker-verifiable source for HS code, tariff, import license, and clearance documents.",
            "Official company or government page for project owner, developer, investor, and responsible office/person.",
            "Academic, library, EIA, or technical report evidence for feasibility assumptions.",
        ],
        "priority_queries": {
            "government_confirmation": official[:6],
            "procurement_tender": procurement[:6],
            "customs_trade": customs[:6],
        },
        "project_confirmation_gate": confirmation_gate,
        "project_execution": {
            "can_create_project_record": False,
            "record_status": confirmation_gate["status"],
            "next_actions": [
                "Open the highest-priority official search URLs and collect title, URL, source date, and snippet.",
                "Attach collected official evidence to /v1/evidence/verify or /v1/projects/pipeline.",
                "Classify the project as planned or under_construction only after official evidence supports it.",
                "Map owner, developer, responsible office/person, tender status, customs impact, and next meeting task.",
                "Request human approval before outreach, quotation, publication, contract, payment, or customer promise.",
            ],
        },
        "blocked_actions": confirmation_gate["blocked_until_confirmed"],
    }


def build_search_expansion(query: str, enriched: dict[str, Any]) -> dict[str, Any]:
    region = enriched.get("region_key") or "central_asia"
    zh_terms = [
        "\u54c8\u8428\u514b\u65af\u5766 \u5de5\u7a0b \u62db\u6807",
        "\u54c8\u8428\u514b\u65af\u5766 EPC \u9879\u76ee",
        "\u54c8\u8428\u514b\u65af\u5766 \u57fa\u7840\u8bbe\u65bd \u6295\u8d44",
        "\u54c8\u8428\u514b\u65af\u5766 \u5728\u5efa\u9879\u76ee",
        "\u54c8\u8428\u514b\u65af\u5766 \u8ba1\u5212\u5efa\u8bbe\u9879\u76ee",
    ]
    en_terms = [
        "Kazakhstan EPC project",
        "Kazakhstan infrastructure tender",
        "Kazakhstan public procurement engineering",
        "Kazakhstan mining infrastructure",
        "Kazakhstan logistics project owner developer",
        "Central Asia EPC opportunity",
    ]
    ru_terms = [
        "\u041a\u0430\u0437\u0430\u0445\u0441\u0442\u0430\u043d \u0438\u043d\u0444\u0440\u0430\u0441\u0442\u0440\u0443\u043a\u0442\u0443\u0440\u043d\u044b\u0439 \u043f\u0440\u043e\u0435\u043a\u0442",
        "\u041a\u0430\u0437\u0430\u0445\u0441\u0442\u0430\u043d \u0442\u0435\u043d\u0434\u0435\u0440 \u0441\u0442\u0440\u043e\u0438\u0442\u0435\u043b\u044c\u0441\u0442\u0432\u043e",
        "\u041a\u0430\u0437\u0430\u0445\u0441\u0442\u0430\u043d EPC \u043f\u043e\u0434\u0440\u044f\u0434\u0447\u0438\u043a",
    ]
    return {
        "original_query": query,
        "region_key": region,
        "chinese_terms": zh_terms,
        "english_terms": en_terms,
        "russian_terms": ru_terms,
        "industry_terms": [
            "EPC",
            "public tender",
            "mining infrastructure",
            "railway logistics",
            "port logistics",
            "industrial park",
        ],
        "risk_terms": ["sanctions compliance", "export control", "customs clearance", "payment risk"],
        "project_stage_terms": ["planned project", "under construction", "tender announced", "contract awarded"],
        "platform_terms": ["government website", "procurement portal", "YouTube", "TikTok", "Douyin", "Telegram"],
        "all_terms": list(dict.fromkeys((enriched.get("queries") or [])[:12] + zh_terms + en_terms + ru_terms)),
    }


def build_source_status(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    status_rows = []
    for source in sources:
        status = str(source.get("status") or "unknown")
        if status == "configured":
            reason = source.get("note") or "Source is configured; live adapter may fetch results at runtime."
            next_action = "Run live adapter and attach returned evidence before confirming facts."
        elif status == "manual_search_url":
            reason = "Manual search URL is available. No live API result has been collected yet."
            next_action = "Open the URL, collect official title/url/date/snippet, then verify evidence."
        elif status == "missing_configuration":
            reason = source.get("reason") or "Missing configuration."
            next_action = "Configure the required key or use the provided manual search URLs."
        else:
            reason = source.get("reason") or "Source status is not classified."
            next_action = "Review source adapter status before relying on results."
        status_rows.append(
            {
                "source": source.get("source"),
                "status": status,
                "result_count": len(source.get("results") or []),
                "reason": reason,
                "next_action": next_action,
            }
        )
    return status_rows


def build_candidate_projects(query: str, enriched: dict[str, Any], project_queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    official_queries = [item for item in project_queries if item.get("intent") == "government_confirmation"][:3]
    tender_queries = [item for item in project_queries if item.get("intent") == "procurement_tender"][:3]
    return [
        {
            "project_name": f"{query} - planned project lead",
            "country": "Kazakhstan" if enriched.get("region_key") == "kazakhstan" else "Central Asia",
            "sector": "engineering trade / infrastructure",
            "stage": "candidate_planned",
            "stage_label": "\u8ba1\u5212\u5efa\u8bbe\u5019\u9009\u9879\u76ee",
            "official_source_status": "not_verified_search_plan_only",
            "owner": "unknown_until_official_evidence_attached",
            "developer": "unknown_until_official_evidence_attached",
            "confidence": 30,
            "risk_flags": [
                "Search plan only; do not treat as a confirmed project.",
                "Government or procurement evidence is required before investment-promotion use.",
            ],
            "next_actions": official_queries + tender_queries,
        }
    ]


def build_result_categories(
    sources: list[dict[str, Any]],
    project_queries: list[dict[str, Any]],
    candidate_projects: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "projects": candidate_projects,
        "official_sources": [item for item in project_queries if item.get("intent") == "government_confirmation"][:8],
        "tenders": [item for item in project_queries if item.get("intent") == "procurement_tender"][:8],
        "risks": [item for item in project_queries if item.get("intent") == "customs_trade"][:8],
        "background": [item for item in project_queries if item.get("intent") == "project_development_intelligence"][:8],
        "social_video": [item for item in sources if item.get("source_type") in {"social_signal", "video_signal"}],
        "research": [item for item in sources if item.get("source_type") in {"academic", "library"}],
    }


def build_project_brief_draft(
    query: str,
    search_expansion: dict[str, Any],
    source_status: list[dict[str, Any]],
    candidate_projects: list[dict[str, Any]],
    confirmation_gate: dict[str, Any],
) -> dict[str, Any]:
    missing = [item for item in source_status if item["status"] == "missing_configuration"]
    return {
        "title": f"Search intelligence brief draft: {query}",
        "status": "draft_not_approved_for_external_use",
        "search_topic": query,
        "summary": "Search expansion and source readiness are prepared. Candidate projects remain leads until official evidence is attached.",
        "enhanced_query_count": len(search_expansion.get("all_terms") or []),
        "source_summary": {
            "total": len(source_status),
            "missing_configuration": len(missing),
            "manual_sources": len([item for item in source_status if item["status"] == "manual_search_url"]),
        },
        "candidate_projects": candidate_projects,
        "official_source_status": confirmation_gate.get("status"),
        "risk_notice": "Do not publish, quote, outreach, or create confirmed project records before official evidence and human approval.",
        "next_actions": [
            "Open government and procurement search URLs first.",
            "Attach official evidence items with title, URL, date, and snippet.",
            "Verify project stage, owner, developer, tender status, customs impact, and risk flags.",
            "Generate feasibility report only as an internal draft until evidence is sufficient.",
        ],
    }


def multi_source_search(query: str) -> dict[str, Any]:
    enriched = enrich_query(query)
    primary_query = enriched["queries"][0] if enriched["queries"] else query
    project_queries = _project_search_queries(query)
    sources: list[dict[str, Any]] = []

    if os.getenv("BING_SEARCH_KEY"):
        sources.append(
            {
                "source": "Bing",
                "status": "configured",
                "source_type": "live_adapter_ready",
                "results": [],
                "note": "Bing key is configured; runtime adapter may fetch live results.",
            }
        )
    else:
        sources.append(
            {
                "source": "Bing",
                "status": "missing_configuration",
                "source_type": "configuration_notice",
                "results": [],
                "reason": "Missing environment variable BING_SEARCH_KEY",
            }
        )

    sources.extend(
        [
            _manual_search("Google", "https://www.google.com/search?q=", primary_query),
            _manual_search("Yandex", "https://yandex.com/search/?text=", primary_query),
            _manual_search("Google Government Confirmation", "https://www.google.com/search?q=", project_queries[0]["query"], source_type="official"),
            _manual_search("Yandex Government Confirmation", "https://yandex.com/search/?text=", project_queries[0]["query"], source_type="official"),
            _manual_search("Google Procurement", "https://www.google.com/search?q=", f"{query} tender procurement EPC", source_type="procurement"),
            _manual_search("OpenAlex", "https://openalex.org/search?q=", f"{query} feasibility study technical report", source_type="academic"),
            _manual_search("Semantic Scholar", "https://www.semanticscholar.org/search?q=", f"{query} feasibility study", source_type="academic"),
            _manual_search("Open Library", "https://openlibrary.org/search?q=", f"{query} infrastructure investment", source_type="library"),
            _manual_search("Telegram", "https://www.google.com/search?q=site%3At.me+", f"{query} project tender", source_type="social_signal"),
            _manual_search("Douyin/Toutiao", "https://www.google.com/search?q=site%3Adouyin.com+OR+site%3Atoutiao.com+", query, source_type="video_signal"),
            _manual_search("TikTok/YouTube", "https://www.google.com/search?q=site%3Atiktok.com+OR+site%3Ayoutube.com+", query, source_type="video_signal"),
        ]
    )

    execution_brief = build_search_execution_brief(query, enriched, project_queries)
    search_expansion = build_search_expansion(query, enriched)
    source_status = build_source_status(sources)
    candidate_projects = build_candidate_projects(query, enriched, project_queries)
    result_categories = build_result_categories(sources, project_queries, candidate_projects)
    project_brief_draft = build_project_brief_draft(
        query,
        search_expansion,
        source_status,
        candidate_projects,
        execution_brief["project_confirmation_gate"],
    )
    return {
        "ok": True,
        "query": query,
        "search_expansion": search_expansion,
        "enrichment": enriched,
        "source_status": source_status,
        "source_readiness": build_source_readiness(sources),
        "result_categories": result_categories,
        "candidate_projects": candidate_projects,
        "project_search_plan": project_queries,
        "project_brief_draft": project_brief_draft,
        "evidence_execution_brief": execution_brief,
        "project_confirmation_gate": execution_brief["project_confirmation_gate"],
        "sources": sources,
        "project_library_rule": "Only create confirmed investment-promotion records after government, customs, procurement, regulator, or official company evidence is attached.",
        "answer_rule": "Final answers must separate verified facts, weak signals, assumptions, risks, and next actions.",
        "safety": "Search only; public posting, outreach, quotation, contract, payment, and customer commitments require human approval.",
    }
