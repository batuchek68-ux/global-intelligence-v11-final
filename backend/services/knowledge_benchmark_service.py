from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.audit_service import append_audit


BACKEND_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_DIR = BACKEND_ROOT / "memory" / "knowledge_base"
BENCHMARK_DIR = BACKEND_ROOT / "memory" / "benchmark"
REPORT_DIR = BACKEND_ROOT / "reports" / "benchmark"


KNOWLEDGE_BASE: dict[str, dict[str, Any]] = {
    "international_trade": {
        "label": "国际贸易",
        "role": "跨境交易工作台，统一处理买方、供应商、代理商、银行、物流、海关和付款风险。",
        "topics": ["Incoterms", "付款条件", "信用证", "供应商尽调", "贸易融资", "出口单证", "代理商风控"],
        "source_priority": ["ICC 规则", "银行文件", "官方贸易门户", "海关公告", "船运和保险单据"],
        "must_do": [
            "把内部建议、草稿和已批准承诺分开标注",
            "核验买方、供应商、收款路径、受益所有人和代理权限",
            "说明交付、保险、清关、付款和汇率假设",
            "报价、合同、付款、交期和客户承诺必须进入人工审批",
        ],
    },
    "customs_information": {
        "label": "海关信息",
        "role": "海关证据工作台，负责 HS 编码、关税、许可证、出口管制、制裁和清关文件核验。",
        "topics": [
            "HS code classification",
            "tariff rate",
            "certificate of origin",
            "customs valuation",
            "import license",
            "export control",
            "sanctions screening",
            "bonded warehouse",
            "temporary import",
            "AEO trusted trader",
            "customs clearance documents",
        ],
        "source_priority": [
            "目标国海关官网",
            "WCO HS 资料",
            "官方税则数据库",
            "贸易部或经济部公告",
            "港口和边境管理机构公告",
            "持牌清关代理书面确认",
        ],
        "search_templates": [
            "{country} customs HS code {product}",
            "{country} import tariff {product} official",
            "{country} customs clearance documents {product}",
            "{country} certificate of origin requirements {product}",
            "{country} export control sanctions customs {product}",
            "{country} temporary import bonded warehouse {product}",
            "site:gov {country} customs tariff {product}",
            "site:customs.gov {country} HS code {product}",
        ],
        "risk_rules": [
            "没有官方海关或持牌清关代理确认时，不得给出最终 HS 编码结论。",
            "关税、许可证、原产地证和清关文件必须记录官方 URL、发布日期或访问日期。",
            "制裁、出口管制、军民两用、政府项目和高风险国家必须进入人工合规复核。",
            "清关时效和费用只能作为估算草稿，不能自动承诺给客户。",
        ],
        "report_template": [
            "结论：当前只能确认哪些官方事实，哪些仍是假设。",
            "证据：海关官网、税则数据库、清关代理、采购文件、产品资料。",
            "风险：HS 争议、关税变化、许可证、原产地、估价、制裁和出口管制。",
            "行动：补证据、问清关代理、复核合同条款、进入人工审批。",
        ],
    },
    "epc_projects": {
        "label": "EPC 工程项目",
        "role": "工程项目工作台，判断计划、在建、招标、业主、开发商、总包、分包和采购机会。",
        "topics": ["FIDIC", "EPC 合同", "招标包", "设计采购施工", "工程进度", "索赔", "变更令", "EIA"],
        "source_priority": ["政府项目页", "招标采购门户", "业主公告", "承包商披露", "EIA 或公众听证材料"],
        "must_do": [
            "把项目阶段标为计划、招标、授标、在建、延期或运营",
            "识别业主、开发商、投资方、总包、主管部门和联系人候选",
            "把官方事实、媒体报道、论坛线索和社交热度分层",
            "合同、索赔、报价、进度和交付承诺必须人工审批",
        ],
    },
    "investment_promotion": {
        "label": "招商引资",
        "role": "招商项目包装工作台，判断价值、成长性、回报潜力、政策支持、投资人匹配和退出路径。",
        "topics": ["项目包装", "开发商图谱", "ROI", "PPP", "产业园区", "优惠政策", "经济特区", "融资结构"],
        "source_priority": ["投资促进署", "政府批复", "开发商官网", "财报", "土地/EIA/规划文件"],
        "must_do": [
            "只有附带政府、监管、采购、海关或官方企业证据后，才可进入招商材料草稿",
            "政策优惠、土地、税收、收益测算必须写明来源和假设",
            "对外路演、投资人沟通和视频发布必须人工批准",
            "把高回报表述改成可核验的情景测算和风险边界",
        ],
    },
    "research": {
        "label": "科研与图书馆资料",
        "role": "科研情报工作台，把论文、标准、专利、数据集、图书馆资料转成工程可执行假设。",
        "topics": ["论文", "数据集", "技术报告", "专利", "标准", "智库", "图书馆资料", "可行性研究"],
        "source_priority": ["同行评审论文", "官方数据集", "大学和图书馆", "标准组织", "政府报告", "专利数据库"],
        "must_do": [
            "把科研结论转成工程参数、适用边界和不确定区间",
            "标注来源类型、日期、样本范围和现实限制",
            "弱证据、二手资料和未复现结论必须降级",
            "不得把文献观点直接当作项目审批事实",
        ],
    },
    "video_media": {
        "label": "视频与媒体",
        "role": "视频制作中心，跟踪 YouTube、TikTok、抖音、视频号和本地平台，生成证据驱动的脚本草稿。",
        "topics": ["短视频脚本", "国家风格", "平台趋势", "证据镜头", "字幕策略", "YouTube", "TikTok", "Douyin"],
        "source_priority": ["平台搜索", "官方频道", "高表现同类视频", "项目照片/视频证据", "受众评论"],
        "must_do": [
            "所有脚本、标题、封面文案和评论回复默认是草稿",
            "不得发布未核验的项目、收益、政策、价格和承诺",
            "学习结构、节奏和镜头语言，但不得复制受保护表达",
            "每条视频草稿都要包含证据镜头、风险提示和审批边界",
        ],
    },
    "political_risk": {
        "label": "政治风险",
        "role": "政治与合规风险工作台，跟踪制裁、出口管制、选举、政策变化、舆情和政府人事变动。",
        "topics": ["制裁", "政策变化", "选举", "政府换届", "公众舆情", "使馆公告", "出口管制"],
        "source_priority": ["政府官网", "监管机构", "使馆公告", "权威新闻", "法律或合规复核"],
        "must_do": [
            "把已确认政策、媒体评论和市场传闻分开",
            "制裁、出口管制、政府项目和第三国政治风险必须升级",
            "重大事项进入老板收件箱",
            "政策或制裁状态不清时，阻断对外承诺和自动发布",
        ],
    },
}


BENCHMARK_QUESTIONS: list[tuple[str, str]] = [
    ("customs_information", "如何确认哈萨克斯坦进口矿山设备的 HS 编码、关税和清关文件？"),
    ("customs_information", "出口到中亚时如何判断是否涉及制裁、军民两用和出口管制？"),
    ("customs_information", "如何用政府官网确认一个产品是否需要进口许可证？"),
    ("customs_information", "海关估价、原产地证和付款条件之间有什么风险关系？"),
    ("customs_information", "如何建立一个国家的海关信息搜索词体系？"),
    ("international_trade", "EPC 设备贸易中 TT、LC、分期付款风险如何判断？"),
    ("international_trade", "如何筛选中亚本地代理商并防止付款风险？"),
    ("international_trade", "Incoterms 如何影响清关、保险和交付责任？"),
    ("international_trade", "如何做一个跨境供应商尽调清单？"),
    ("international_trade", "如何判断客户询盘是否真实且值得跟进？"),
    ("epc_projects", "如何识别在建 EPC 项目的业主、总包和分包机会？"),
    ("epc_projects", "如何从招标公告反推项目阶段和采购需求？"),
    ("epc_projects", "FIDIC 合同中哪些条款必须人工审查？"),
    ("epc_projects", "如何跟踪港口、矿山、物流园区建设项目？"),
    ("epc_projects", "项目延期时如何判断索赔和沟通风险？"),
    ("investment_promotion", "如何把一个计划建设项目包装成招商引资材料？"),
    ("investment_promotion", "如何判断一个工业园区项目是否具有高回报潜力？"),
    ("investment_promotion", "如何确认项目开发者、投资方和政府主管部门？"),
    ("investment_promotion", "招商材料中哪些表述不能自动发布？"),
    ("investment_promotion", "如何按国家生成招商引资可行性报告草稿？"),
    ("research", "如何同时搜索学术论文、图书馆资料和政府报告？"),
    ("research", "如何评价一个技术路线是否适合工程项目？"),
    ("research", "如何把科研资料转成项目决策简报？"),
    ("research", "如何建立证据等级和引用规则？"),
    ("research", "如何避免用二手资料做最终判断？"),
    ("video_media", "如何为哈萨克斯坦工程项目制作短视频脚本？"),
    ("video_media", "如何跟踪 YouTube、TikTok、抖音同类视频并优化表达？"),
    ("video_media", "不同国家项目视频风格如何区分？"),
    ("video_media", "公开视频中哪些内容必须人工审查？"),
    ("video_media", "如何把项目情报变成 60 秒招商视频？"),
    ("political_risk", "政策变化如何影响跨境工程贸易？"),
    ("political_risk", "如何判断政府换届对项目推进的影响？"),
    ("political_risk", "制裁新闻出现后项目是否应该暂停？"),
    ("political_risk", "如何跟踪中亚政治风险和论坛关注度？"),
    ("political_risk", "哪些政治风险必须进入老板收件箱？"),
    ("customs_information", "如何确认设备是否能进入保税仓或临时进口？"),
    ("international_trade", "如何设计不承诺价格的客户回复草稿？"),
    ("epc_projects", "如何对比两个 EPC 项目的优先级？"),
    ("investment_promotion", "如何判断一个项目是否适合中国企业参与？"),
    ("research", "如何把论文结论转成可执行工程建议？"),
    ("video_media", "如何从爆款视频提取可学习但不抄袭的结构？"),
    ("political_risk", "如何建立政治风险预警关键词？"),
    ("customs_information", "如何核验清关代理给出的税费估算？"),
    ("international_trade", "如何建立客户、供应商、代理商三方风控表？"),
    ("epc_projects", "如何用政府采购平台跟踪项目招标变更？"),
    ("investment_promotion", "如何写一页纸项目投资摘要？"),
    ("research", "如何建立行业知识库并持续更新？"),
    ("video_media", "如何根据国家文化调整视频开场和字幕？"),
    ("political_risk", "如何判断项目是否受国际关系影响？"),
    ("customs_information", "如何生成海关信息可核验报告草稿？"),
]


SCORING_DIMENSIONS: dict[str, dict[str, Any]] = {
    "accuracy": {
        "label": "准确性",
        "keywords": ["official", "verified", "source", "date", "evidence", "准确", "官方", "核验", "政府官网", "来源日期"],
        "weight": 1.15,
    },
    "evidence": {
        "label": "证据",
        "keywords": ["url", "citation", "government", "customs", "report", "source", "证据", "官网", "海关", "链接"],
        "weight": 1.2,
    },
    "actionability": {
        "label": "可执行性",
        "keywords": ["next step", "checklist", "workflow", "流程", "步骤", "清单", "建议", "执行", "行动项"],
        "weight": 1.1,
    },
    "risk_judgment": {
        "label": "风险判断",
        "keywords": ["risk", "approval", "sanction", "export control", "customs", "风险", "审批", "制裁", "出口管制", "人工复核"],
        "weight": 1.2,
    },
    "professional_depth": {
        "label": "专业深度",
        "keywords": ["HS code", "Incoterms", "EPC", "FIDIC", "tariff", "customs valuation", "LC", "专业", "关税", "海关估价"],
        "weight": 1.0,
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _knowledge_path() -> Path:
    return Path(os.getenv("V11_KNOWLEDGE_BASE_PATH", str(KNOWLEDGE_DIR / "industry_knowledge.json")))


def _benchmark_path() -> Path:
    return Path(os.getenv("V11_BENCHMARK_PATH", str(BENCHMARK_DIR / "v11_benchmark_50.json")))


def build_industry_knowledge_base() -> dict[str, Any]:
    path = _knowledge_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "updated_at": _now_iso(),
        "purpose": "v11 垂直行业知识库：国际贸易、EPC、招商、科研、视频、政治风险、海关信息。",
        "domains": KNOWLEDGE_BASE,
        "operating_rule": [
            "回答必须像专业执行团队：结论、证据、风险、行动清单、人工审批边界。",
            "政府、海关、采购、监管和官方企业证据优先级高于媒体、论坛和社交信号。",
            "对外消息、报价、合同、付款、客户承诺和公开视频必须人工审批。",
            "每次沉淀新经验时，优先补入搜索词、证据规则、风险规则和报告模板。",
        ],
        "quality_rule": "每个专业回答都必须说明证据、下一步、风险边界和是否需要人工批准。",
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    append_audit(
        "KNOWLEDGE_BASE_UPDATED",
        "DONE",
        "Built readable vertical industry knowledge base with customs information, customs report template, and approval rules.",
        confidence=95,
        risk="LOW",
    )
    return {"ok": True, "path": str(path), "data": data}


def build_v11_benchmark() -> dict[str, Any]:
    path = _benchmark_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    questions = [
        {
            "id": f"v11-benchmark-{index:02d}",
            "domain": domain,
            "question": question,
            "expected_answer_traits": [
                "清晰结论",
                "证据来源和核验要求",
                "可执行下一步",
                "风险和人工审批边界",
                "专业术语和行业深度",
                "区分已核验事实、弱信号、假设和建议",
                "必要时生成项目推进包、证据包或沟通草稿",
            ],
            "compare_targets": ["v11", "Doubao", "Yuanbao"],
        }
        for index, (domain, question) in enumerate(BENCHMARK_QUESTIONS, start=1)
    ]
    data = {
        "updated_at": _now_iso(),
        "question_count": len(questions),
        "purpose": "用 50 个真实工作问题对比 v11、豆包、元宝的有用性、证据、可执行性、风险控制和专业深度。",
        "winner_rule": "v11 wins only when it gives clearer evidence, safer risk judgment, and more executable project work than generic assistants.",
        "questions": questions,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    append_audit(
        "V11_BENCHMARK_BUILT",
        "DONE",
        f"Built {len(questions)} readable benchmark questions for v11/Doubao/Yuanbao comparison.",
        confidence=95,
        risk="LOW",
    )
    return {"ok": True, "path": str(path), "data": data}


def _dimension_score(text: str, keywords: list[str], weight: float) -> dict[str, Any]:
    hits = [keyword for keyword in keywords if keyword.lower() in text]
    raw = 35 + len(hits) * 12
    score = min(100, round(raw * weight))
    return {"score": score, "hits": hits}


def score_answer(question: str, answer: str, *, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    text = f"{question}\n{answer}".lower()
    evidence = evidence or []
    dimensions: dict[str, dict[str, Any]] = {}
    for name, spec in SCORING_DIMENSIONS.items():
        dimensions[name] = _dimension_score(text, spec["keywords"], float(spec["weight"]))
        dimensions[name]["label"] = spec["label"]

    if evidence:
        dimensions["evidence"]["score"] = min(100, dimensions["evidence"]["score"] + 18)
        dimensions["accuracy"]["score"] = min(100, dimensions["accuracy"]["score"] + 6)
    if "approval" in text or "审批" in text or "人工" in text:
        dimensions["risk_judgment"]["score"] = min(100, dimensions["risk_judgment"]["score"] + 8)
    if "checklist" in text or "清单" in text or "步骤" in text:
        dimensions["actionability"]["score"] = min(100, dimensions["actionability"]["score"] + 6)

    overall = round(sum(item["score"] for item in dimensions.values()) / len(dimensions))
    verdict = "excellent" if overall >= 85 else ("usable" if overall >= 70 else "needs_improvement")
    return {
        "ok": True,
        "created_at": _now_iso(),
        "overall_score": overall,
        "verdict": verdict,
        "dimensions": dimensions,
        "recommendations": [
            "增加官方来源 URL 和发布日期或访问日期。",
            "区分已核验事实、弱信号、假设和建议。",
            "把结论转成下一步行动清单。",
            "明确风险、人工审批边界和阻断动作。",
            "使用行业术语时说明含义、证据和适用范围。",
        ],
    }


def compare_answers(question: str, answers: dict[str, str]) -> dict[str, Any]:
    scored = {name: score_answer(question, answer) for name, answer in answers.items()}
    ranked = sorted(scored.items(), key=lambda item: item[1]["overall_score"], reverse=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "latest_comparison.json"
    result = {
        "ok": True,
        "created_at": _now_iso(),
        "question": question,
        "ranked": [{"name": name, "score": data["overall_score"], "verdict": data["verdict"]} for name, data in ranked],
        "scores": scored,
        "rule": "分数越高，代表证据、执行、风险边界和专业深度越强。",
    }
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result | {"path": str(report_path)}
