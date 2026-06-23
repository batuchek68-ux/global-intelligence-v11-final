from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.services.audit_service import append_audit
from backend.services.evidence_verification_service import build_evidence_dossier
from backend.services.intelligence_center_service import build_intelligence_search_system, build_video_production_center
from backend.services.knowledge_benchmark_service import score_answer
from backend.services.project_action_board_service import build_action_board
from backend.services.project_intelligence_service import build_project_search_plan


BACKEND_ROOT = Path(__file__).resolve().parents[1]
RESPONSE_MEMORY_DIR = BACKEND_ROOT / "memory" / "team_responses"
RESPONSE_REPORT_DIR = BACKEND_ROOT / "reports" / "team_responses"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _memory_dir() -> Path:
    override = os.getenv("V11_TEAM_RESPONSE_MEMORY_DIR")
    return Path(override) if override else RESPONSE_MEMORY_DIR


def _report_dir() -> Path:
    override = os.getenv("V11_TEAM_RESPONSE_REPORT_DIR")
    return Path(override) if override else RESPONSE_REPORT_DIR


def _stable_id(*parts: str) -> str:
    raw = "|".join(str(part).strip().lower() for part in parts if part)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _as_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or fallback
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()] or [value.strip()]
    return fallback


def _detect_country(question: str, metadata: dict[str, Any]) -> str:
    if metadata.get("country"):
        return str(metadata["country"]).strip()
    lower = question.lower()
    if "kazakhstan" in lower or "哈萨克斯坦" in question:
        return "Kazakhstan"
    if "indonesia" in lower or "印度尼西亚" in question or "印尼" in question:
        return "Indonesia"
    if "uzbekistan" in lower or "乌兹别克斯坦" in question:
        return "Uzbekistan"
    if "kyrgyzstan" in lower or "吉尔吉斯斯坦" in question:
        return "Kyrgyzstan"
    return "Kazakhstan"


def build_team_response_pack(
    question: str,
    *,
    metadata: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    metadata = metadata or {}
    evidence = evidence or []
    country = _detect_country(question, metadata)
    industries = _as_list(metadata.get("industries") or metadata.get("industry"), ["infrastructure", "mining", "logistics", "energy"])
    response_id = _stable_id(question, country, ",".join(industries), _now_iso()[:10])

    dossier = build_evidence_dossier(question, evidence, project=str(metadata.get("project") or ""), country=country)
    search_plan = build_project_search_plan(question, country)
    intelligence_system = build_intelligence_search_system([question], [country], industries)
    video_center = build_video_production_center([question], [country], industries[:2])
    case = {
        "created_at": _now_iso(),
        "project": {
            "title": str(metadata.get("project") or question[:80]),
            "country": country,
            "stage": str(metadata.get("stage") or "intelligence_response"),
            "next_decision": "Approve external use only after evidence and risk review.",
        },
        "classification": {"is_major_matter": dossier["requires_human_review"]},
        "judgment": {
            "level": "high" if dossier["requires_human_review"] else "medium",
            "score": max(50, 100 - int(dossier["confidence"] or 0)),
        },
    }
    action_board = build_action_board(case, dossier)
    executive_answer = _build_executive_answer(question, country, dossier, action_board)
    roles = _build_role_outputs(question, country, dossier, search_plan, video_center, action_board)
    quality = score_answer(
        question,
        executive_answer + "\n" + "\n".join(item["contribution"] for item in roles),
        evidence=evidence,
    )
    pack = {
        "ok": True,
        "id": response_id,
        "created_at": _now_iso(),
        "question": question,
        "country": country,
        "industries": industries,
        "mode": "team_response_pack",
        "executive_answer": executive_answer,
        "evidence_status": {
            "verification_status": dossier["verification_status"],
            "confidence": dossier["confidence"],
            "requires_human_review": dossier["requires_human_review"],
            "official_sources": dossier["summary"]["official_sources"],
        },
        "team_roles": roles,
        "search_plan": {
            "official_queries": [item for item in search_plan["queries"] if item["intent"] == "government_confirmation"][:8],
            "intelligence_categories": [
                {"id": item["id"], "label": item["label"], "first_search_term": item["search_terms"][0] if item["search_terms"] else ""}
                for item in intelligence_system["categories"][:9]
            ],
        },
        "video_plan": {
            "platform_searches": video_center["platform_searches"][:12],
            "script_templates": video_center["script_templates"],
        },
        "action_board": {
            "risk_gate": action_board["risk_gate"],
            "summary": action_board["summary"],
            "tasks": action_board["tasks"],
        },
        "quality_score": quality,
        "approval_boundary": {
            "draft_only": True,
            "blocked_actions": dossier["blocked_actions"],
            "human_approval_required": dossier["requires_human_review"],
        },
        "rules": [
            "像一个项目团队一样回答：结论、证据、行动、风险、审批边界。",
            "论坛、社交、视频和聊天信号只能作为关注度线索，不能当作官方事实。",
            "外联、报价、合同、付款、客户承诺和公开视频发布必须人工审批。",
        ],
    }
    if persist:
        return write_team_response_pack(pack)
    return {"ok": True, "pack": pack}


def _build_executive_answer(question: str, country: str, dossier: dict[str, Any], action_board: dict[str, Any]) -> str:
    if dossier["verification_status"] == "officially_supported":
        conclusion = "可以作为内部推进依据；对外使用仍需要人工审批。"
    elif dossier["verification_status"] == "partially_supported":
        conclusion = "可以进入内部尽调和任务推进；暂时不能作为正式对外结论。"
    else:
        conclusion = "目前只能作为线索；必须先补政府、海关、采购、监管或官方企业证据。"
    return (
        f"结论: {conclusion}\n"
        f"问题: {question}\n"
        f"国家/地区: {country}\n"
        f"证据状态: {dossier['verification_status']}；置信度 {dossier['confidence']}；官方证据 {dossier['summary']['official_sources']} 条。\n"
        f"任务状态: {action_board['risk_gate']['status']}；需要处理 {action_board['summary']['task_count']} 项任务；阻断 {action_board['summary']['blocked_count']} 项高风险动作。\n"
        "执行清单: 先查官方 source URL 和 source date，再核验 government/customs/procurement evidence；随后形成 next step checklist、risk approval gate、项目库记录和可行性草稿。\n"
        "专业判断: 海关问题必须核验 HS code、tariff、customs valuation、certificate of origin、import license；EPC 项目必须核验 owner、developer、contractor、FIDIC/contract risk 和 tender status。\n"
        "风险边界: payment、contract、sanction、export control、customs、quotation、delivery promise、public publishing 必须 approval 后才能对外使用。"
    )


def _build_role_outputs(
    question: str,
    country: str,
    dossier: dict[str, Any],
    search_plan: dict[str, Any],
    video_center: dict[str, Any],
    action_board: dict[str, Any],
) -> list[dict[str, Any]]:
    blocked = dossier["requires_human_review"]
    first_official_query = next((item["query"] for item in search_plan["queries"] if item["intent"] == "government_confirmation"), question)
    first_video_platform = video_center["platform_searches"][0]["platform"] if video_center.get("platform_searches") else "YouTube/TikTok/Douyin"
    return [
        {
            "role": "trade_lead",
            "label": "国际贸易负责人",
            "contribution": f"先核验 {country} 官方海关 source URL/date、HS code、tariff、customs valuation、Incoterms、payment risk 和物流路径；未核验前不承诺价格、交期或清关结果。",
            "next_step": "收集海关官网、官方税则、清关文件、银行付款条件证据，并形成可执行 checklist。",
        },
        {
            "role": "research_analyst",
            "label": "科研情报分析",
            "contribution": f"优先搜索 official government、procurement、academic paper、library report 来源；第一条官方检索式: {first_official_query}",
            "next_step": "把证据分为政府/采购/企业/媒体/社交五级，记录 citation、URL、source date、relevance note。",
        },
        {
            "role": "investment_promotion_lead",
            "label": "招商引资负责人",
            "contribution": "只有在项目业主、developer、investor、government authority、ROI、PPP/incentive 被官方证据确认后，才能形成招商材料草稿。",
            "next_step": "建立 owner/developer/investor/government authority 四类名单，并标注 evidence level。",
        },
        {
            "role": "video_media_producer",
            "label": "视频传播负责人",
            "contribution": f"视频只做内部草稿，参考 {first_video_platform} 等平台的节奏、国家风格和证据镜头，不复制内容，不发布未经审批的承诺。",
            "next_step": "生成 60 秒项目机会脚本、风险解释脚本和平台关键词，等待人工审批。",
        },
        {
            "role": "project_manager",
            "label": "项目经理",
            "contribution": f"任务板已生成 {action_board['summary']['task_count']} 项，阻断 {action_board['summary']['blocked_count']} 项；每项都要有 owner、deadline、evidence、next step。",
            "next_step": "安排责任人、截止时间、会议议程、decision log 和复盘记录。",
        },
        {
            "role": "risk_approval_officer",
            "label": "风控审批负责人",
            "contribution": "正式外联、quotation、contract、payment、sanction/export control、delivery promise、public publishing 全部进入 approval gate。",
            "next_step": "把高风险事项写入老板收件箱，审批前保持 DRAFT - Not approved for sending。",
            "blocked": blocked,
        },
    ]


def render_team_response_pack(pack: dict[str, Any]) -> str:
    lines = [
        f"# v11 Team Response Pack: {pack.get('question')}",
        "",
        "DRAFT - internal team response, not approved for external sending",
        "",
        "## Executive Answer",
        "",
        pack.get("executive_answer", ""),
        "",
        "## Team Roles",
        "",
    ]
    for role in pack.get("team_roles", []):
        lines.append(f"### {role['label']}")
        lines.append(f"- Contribution: {role['contribution']}")
        lines.append(f"- Next step: {role['next_step']}")
        lines.append("")
    lines.extend(["## Approval Boundary", ""])
    boundary = pack.get("approval_boundary", {})
    lines.append(f"- Human approval required: {boundary.get('human_approval_required')}")
    for item in boundary.get("blocked_actions", []):
        lines.append(f"- Blocked: {item}")
    lines.extend(["", "## Quality Score", ""])
    score = pack.get("quality_score", {})
    lines.append(f"- Overall: {score.get('overall_score')} ({score.get('verdict')})")
    lines.append("")
    return "\n".join(lines)


def write_team_response_pack(pack: dict[str, Any]) -> dict[str, Any]:
    memory_dir = _memory_dir()
    report_dir = _report_dir()
    memory_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = memory_dir / f"{pack['id']}.json"
    report_path = report_dir / f"{pack['id']}.md"
    latest_json = memory_dir / "latest.json"
    latest_md = report_dir / "latest.md"
    json_text = json.dumps(pack, ensure_ascii=False, indent=2)
    report_text = render_team_response_pack(pack)
    json_path.write_text(json_text, encoding="utf-8")
    report_path.write_text(report_text, encoding="utf-8")
    latest_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(report_text, encoding="utf-8")
    append_audit(
        "TEAM_RESPONSE_PACK_WRITTEN",
        "DONE",
        f"Team response pack id={pack['id']} question={pack['question'][:120]} score={pack['quality_score']['overall_score']}",
        confidence=93,
        risk="MEDIUM" if pack["approval_boundary"]["human_approval_required"] else "LOW",
    )
    return {"ok": True, "pack": pack, "json_path": str(json_path), "report_path": str(report_path)}
