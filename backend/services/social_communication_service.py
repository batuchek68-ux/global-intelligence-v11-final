from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.comm.chat_gateway import build_chat_reply_draft, save_chat_reply_draft
from backend.services.audit_service import append_audit


HIGH_RISK_TERMS = [
    "contract",
    "price",
    "quote",
    "payment",
    "delivery date",
    "guarantee",
    "sanction",
    "export control",
    "legal",
    "sign",
    "commit",
    "合同",
    "签约",
    "报价",
    "价格",
    "付款",
    "交期",
    "保证",
    "制裁",
    "出口管制",
    "法律",
    "承诺",
]

FACT_REQUIRED_TERMS = [
    "project owner",
    "developer",
    "government",
    "tender",
    "official",
    "investment",
    "project",
    "项目业主",
    "开发商",
    "政府",
    "招标",
    "官方",
    "投资",
    "项目",
]

CHANNEL_TONE = {
    "wechat": "简短、礼貌、关系友好、不做正式承诺",
    "enterprise_wechat": "商务清晰、行动项明确、带审批意识",
    "telegram": "直接、简短、先证据后判断",
    "linkedin": "专业、证据优先、不披露敏感信息",
    "email": "结构化、可追溯、正式但仍为草稿",
    "feishu": "团队协作式、任务明确、审批边界清楚",
    "tiktok": "公开视频草稿、短句、无未核实承诺",
    "youtube": "教育解释型、证据导向、无投资承诺",
    "douyin": "短视频草稿、抓重点、不得发布未审批内容",
}


@dataclass
class CommunicationDecision:
    authorized: bool
    risk_level: str
    confidence: int
    action: str
    needs_human_approval: bool
    reasons: list[str]


def _official_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item for item in evidence
        if isinstance(item, dict)
        if str(item.get("source_type", "")).lower() in {"government", "official", "procurement", "customs"}
        or ".gov" in str(item.get("url", "")).lower()
        or "gov." in str(item.get("url", "")).lower()
    ]


def assess_social_context(
    channel: str,
    message: str,
    *,
    authorization: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    audience: str = "external",
) -> dict[str, Any]:
    authorization = authorization or {}
    evidence = evidence or []
    text = f"{channel} {message} {audience}".lower()
    high_risk_hits = [term for term in HIGH_RISK_TERMS if term.lower() in text]
    fact_required_hits = [term for term in FACT_REQUIRED_TERMS if term.lower() in text]
    official_evidence = _official_evidence(evidence)
    authorized = bool(authorization.get("approved_by_human") or authorization.get("scope") == "draft_only")
    send_authorized = bool(authorization.get("approved_by_human") and authorization.get("allow_send"))

    reasons: list[str] = []
    if high_risk_hits:
        reasons.append(f"High-risk terms detected: {', '.join(high_risk_hits[:6])}")
    if fact_required_hits and not official_evidence:
        reasons.append("Official, customs, or procurement evidence is required before factual project claims.")
    if audience != "internal" and not send_authorized:
        reasons.append("External communication is not authorized for sending.")
    if channel.lower() in {"tiktok", "youtube", "douyin", "video_channel"}:
        reasons.append("Public platform content must remain draft until approval.")

    needs_human_approval = bool(high_risk_hits or (audience != "internal" and not send_authorized))
    if fact_required_hits and not official_evidence:
        needs_human_approval = True

    confidence = 92
    if high_risk_hits:
        confidence -= 18
    if fact_required_hits and not official_evidence:
        confidence -= 16
    if not authorized:
        confidence -= 12
    confidence = max(35, confidence)

    action = "send_allowed" if send_authorized and not needs_human_approval else "draft_only"
    risk_level = "high" if high_risk_hits else ("medium" if needs_human_approval else "low")

    decision = CommunicationDecision(
        authorized=authorized,
        risk_level=risk_level,
        confidence=confidence,
        action=action,
        needs_human_approval=needs_human_approval,
        reasons=reasons or ["Low-risk internal or approved communication path."],
    )
    return {
        "authorized": decision.authorized,
        "risk_level": decision.risk_level,
        "confidence": decision.confidence,
        "action": decision.action,
        "needs_human_approval": decision.needs_human_approval,
        "reasons": decision.reasons,
        "tone": CHANNEL_TONE.get(channel.lower(), "专业、证据优先、审批边界清楚"),
        "official_evidence_count": len(official_evidence),
        "boundary": "The system may draft and analyze; sending requires explicit human approval and channel authorization.",
    }


def _build_internal_review(channel: str, inbound_message: str, assessment: dict[str, Any]) -> dict[str, Any]:
    return {
        "channel": channel,
        "risk_level": assessment["risk_level"],
        "confidence": assessment["confidence"],
        "team_judgment": [
            "商务负责人: 先确认对方诉求、项目背景、付款和交付边界，不承诺价格或交期。",
            "情报负责人: 补充官方项目、业主、开发商、招标、海关和政策证据。",
            "项目经理: 把沟通转成会议议程、责任人、截止时间和下一步任务。",
            "风控负责人: 合同、报价、付款、制裁、出口管制、公开视频发布全部进入人工审批。",
        ],
        "inbound_summary": inbound_message[:500],
        "reasons": assessment["reasons"],
    }


def _build_reply_message(channel: str, assessment: dict[str, Any]) -> str:
    evidence_line = (
        "目前已有官方证据可作为内部核验基础。"
        if assessment["official_evidence_count"]
        else "目前还缺少官方证据，不能把项目、价格、交期或合作承诺作为正式结论。"
    )
    return (
        "DRAFT - Not approved for sending\n"
        f"Channel: {channel}\n"
        f"Tone: {assessment['tone']}\n\n"
        "拟回复:\n"
        "您好，信息已收到。我们会先核验项目官方来源、业主/开发商、招标或采购状态、海关与合规风险，"
        "再整理下一步沟通清单。\n"
        f"{evidence_line}\n"
        "在完成内部证据核验和人工审批前，我们不能正式承诺报价、付款条件、交期、合同条款或公开发布内容。\n"
        "如您方便，请先补充项目官网链接、招标/采购编号、负责人信息和关键时间节点，我们会按证据清单推进。"
    )


def build_authorized_social_reply(
    channel: str,
    recipient: str,
    inbound_message: str,
    *,
    authorization: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    audience: str = "external",
) -> dict[str, Any]:
    assessment = assess_social_context(
        channel,
        inbound_message,
        authorization=authorization,
        evidence=evidence,
        audience=audience,
    )
    internal_review = _build_internal_review(channel, inbound_message, assessment)
    approval_checklist = [
        "确认是否已经完成人工审批并允许对外发送，而不只是生成草稿。",
        "确认项目事实是否已有官方/海关/采购/企业证据支持。",
        "确认回复中没有报价、付款、交期、合同、法律、制裁或出口管制承诺。",
        "确认公开视频、社交平台、微信/飞书/邮件内容已由负责人批准。",
    ]
    message = _build_reply_message(channel, assessment)
    draft = build_chat_reply_draft(
        channel=channel,
        recipient=recipient,
        message=message,
        context={
            "inbound_message": inbound_message,
            "assessment": assessment,
            "internal_review": internal_review,
            "approval_checklist": approval_checklist,
            "authorization": authorization or {},
            "evidence": evidence or [],
        },
    )
    path = save_chat_reply_draft(draft)
    append_audit(
        "SOCIAL_COMMUNICATION_ANALYZED",
        "DRAFT_ONLY" if assessment["action"] == "draft_only" else "SEND_ALLOWED_PENDING_GATEWAY",
        f"channel={channel} recipient={recipient} risk={assessment['risk_level']} confidence={assessment['confidence']}",
        confidence=int(assessment["confidence"]),
        risk=assessment["risk_level"].upper(),
    )
    return {
        "ok": True,
        "assessment": assessment,
        "internal_review": internal_review,
        "approval_checklist": approval_checklist,
        "draft": draft,
        "draft_path": str(path),
        "sent": False,
    }
