from __future__ import annotations

from typing import Any


def _contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.metrics = {"executions": 0, "errors": 0}

    async def execute_async(self, input_data: dict[str, Any], org_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def execute(self, input_data: dict[str, Any], org_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def _done(self, data: dict[str, Any]) -> dict[str, Any]:
        self.metrics["executions"] += 1
        return data


class ClassifierAgent(BaseAgent):
    def __init__(self):
        super().__init__("classifier")

    async def execute_async(self, input_data: dict[str, Any], org_id: str) -> dict[str, Any]:
        query = str(input_data.get("query") or "")
        intent = "project_execution"
        if _contains_any(query, ["customs", "tariff", "hs code", "海关", "关税", "清关"]):
            intent = "customs_trade_risk"
        elif _contains_any(query, ["video", "youtube", "tiktok", "douyin", "抖音", "视频", "视频号"]):
            intent = "video_media_plan"
        elif _contains_any(query, ["research", "paper", "library", "科研", "论文", "学术", "图书馆"]):
            intent = "research_intelligence"
        elif _contains_any(query, ["investment", "招商", "investor", "developer", "投资", "开发商"]):
            intent = "investment_promotion"
        return self._done(
            {
                "intent": intent,
                "confidence": 0.9,
                "query": query,
                "operating_mode": "vertical_industry_team",
            }
        )


class ExtractorAgent(BaseAgent):
    def __init__(self):
        super().__init__("extractor")

    async def execute_async(self, input_data: dict[str, Any], org_id: str) -> dict[str, Any]:
        query = str(input_data.get("query") or "")
        countries: list[str] = []
        if _contains_any(query, ["kazakhstan", "哈萨克斯坦"]):
            countries.append("Kazakhstan")
        if _contains_any(query, ["indonesia", "印尼", "印度尼西亚"]):
            countries.append("Indonesia")
        if _contains_any(query, ["uzbekistan", "乌兹别克斯坦"]):
            countries.append("Uzbekistan")
        if _contains_any(query, ["central asia", "中亚"]):
            countries.append("Central Asia")
        if not countries:
            countries.append("Kazakhstan")

        risk_terms = [
            term
            for term in [
                "customs",
                "tariff",
                "payment",
                "contract",
                "sanction",
                "export control",
                "海关",
                "关税",
                "付款",
                "合同",
                "制裁",
                "出口管制",
                "报价",
                "承诺",
            ]
            if _contains_any(query, [term])
        ]
        return self._done(
            {
                "countries": countries,
                "keywords": [item for item in query.replace(",", " ").split() if item],
                "risk_terms": risk_terms,
                "entities_required": [
                    "project_owner",
                    "developer",
                    "government_authority",
                    "responsible_person",
                    "customs_authority",
                    "procurement_contact",
                ],
            }
        )


class EvidencePlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__("evidence_planner")

    async def execute_async(self, input_data: dict[str, Any], org_id: str) -> dict[str, Any]:
        query = str(input_data.get("query") or "")
        metadata = input_data.get("metadata") if isinstance(input_data.get("metadata"), dict) else {}
        extracted = input_data.get("prev_task_2", {})
        country = str(metadata.get("country") or (extracted.get("countries") or ["Kazakhstan"])[0])
        return self._done(
            {
                "country": country,
                "required_sources": [
                    "government project page",
                    "official procurement or tender page",
                    "customs authority, tariff, HS code, and import document source",
                    "official owner, developer, investor, or regulator announcement",
                    "academic, patent, library, or standards source for technical feasibility",
                    "reputable media plus social/video signals for attention tracking only",
                ],
                "search_queries": [
                    f'{country} "{query}" official government project owner developer',
                    f'{country} "{query}" tender procurement EPC contractor',
                    f'{country} customs HS code tariff import documents "{query}"',
                    f'{country} investment promotion "{query}" investor developer official',
                    f'{country} "{query}" feasibility study EIA ministry akimat',
                    f'{country} "{query}" YouTube TikTok Douyin Telegram forum public attention',
                ],
                "evidence_rule": "Government, customs, procurement, regulator, and official company pages are required before outreach or feasibility conclusions.",
            }
        )


class RiskGateAgent(BaseAgent):
    def __init__(self):
        super().__init__("risk_gate")

    async def execute_async(self, input_data: dict[str, Any], org_id: str) -> dict[str, Any]:
        extracted = input_data.get("prev_task_2", {})
        evidence_plan = input_data.get("prev_task_3", {})
        risk_terms = extracted.get("risk_terms", [])
        needs_approval = bool(risk_terms)
        return self._done(
            {
                "needs_human_approval": needs_approval,
                "risk_terms": risk_terms,
                "minimum_evidence": evidence_plan.get("required_sources", [])[:4],
                "blocked_actions": [
                    "external commitment",
                    "formal quotation",
                    "contract or payment approval",
                    "delivery promise",
                    "public publishing",
                    "official social reply",
                ],
                "allowed_actions": [
                    "internal draft",
                    "search plan",
                    "evidence checklist",
                    "project task board",
                    "human approval request",
                ],
            }
        )


class SynthesizerAgent(BaseAgent):
    def __init__(self):
        super().__init__("synthesizer")

    async def execute_async(self, input_data: dict[str, Any], org_id: str) -> dict[str, Any]:
        results = {
            "task_1": input_data.get("prev_task_1", {}),
            "task_2": input_data.get("prev_task_2", {}),
            "task_3": input_data.get("prev_task_3", {}),
            "task_4": input_data.get("prev_task_4", {}),
        }
        return self._done(await self.synthesize(results, str(input_data.get("query") or "")))

    async def synthesize(self, results: dict[str, Any], original_query: str) -> dict[str, Any]:
        classifier = results.get("task_1", {})
        extracted = results.get("task_2", {})
        evidence = results.get("task_3", {})
        risk = results.get("task_4", {})
        return self._done(
            {
                "title": "v11 industry team orchestration result",
                "query": original_query,
                "intent": classifier.get("intent", "project_execution"),
                "countries": extracted.get("countries", []),
                "evidence_plan": evidence.get("required_sources", []),
                "search_queries": evidence.get("search_queries", []),
                "risk_gate": risk,
                "team_next_steps": [
                    "Trade lead verifies customs, payment, Incoterms, logistics, and contract risk.",
                    "Research analyst grades government, procurement, academic, library, media, social, and video evidence.",
                    "Investment lead maps project owner, developer, investor, authority, and promotion gap.",
                    "Video producer drafts internal scripts from verified facts and platform keyword trends only.",
                    "Project manager turns findings into tasks, deadlines, meeting agenda, and decision queue.",
                    "Risk officer blocks external commitments until human approval is recorded.",
                ],
                "status": "team_orchestration_ready",
            }
        )


class AgentPool:
    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}
        self._init_agents()

    def _init_agents(self) -> None:
        self.agents = {
            "classifier": ClassifierAgent(),
            "extractor": ExtractorAgent(),
            "evidence_planner": EvidencePlannerAgent(),
            "risk_gate": RiskGateAgent(),
            "synthesizer": SynthesizerAgent(),
        }

    def get_agent(self, agent_type: str) -> BaseAgent | None:
        return self.agents.get(agent_type)

    def get_all_agents(self) -> dict[str, BaseAgent]:
        return self.agents

    def health_check(self) -> dict[str, Any]:
        return {
            "total_agents": len(self.agents),
            "agents": list(self.agents.keys()),
            "status": "healthy",
            "mode": "v11_vertical_industry_team",
        }
