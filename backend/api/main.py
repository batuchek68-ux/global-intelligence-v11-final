from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
for path in (PROJECT_ROOT, BACKEND_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.core.agents import AgentPool
from backend.core.orchestration import OrchestrationEngine
from backend.security.tenant_isolation import TenantIsolationManager
from backend.services.cloud_service import cloud_check, cloud_run_requested, cloud_status
from backend.services.evidence_verification_service import verify_claim
from backend.services.license_service import core_allowed, license_status
from backend.services import knowledge_ingest_service
from backend.services import core_retrieval_service
from backend.services.intelligence_center_service import (
    build_intelligence_search_system,
    build_video_production_center,
    generate_intelligence_brief,
    read_keyword_bank,
)
from backend.services.industry_war_room_service import build_industry_war_room
from backend.services.knowledge_benchmark_service import (
    build_industry_knowledge_base,
    build_v11_benchmark,
    compare_answers,
    score_answer,
)
from backend.services.mission_control_service import write_mission_control
from backend.services.project_action_board_service import build_and_write_action_board
from backend.services.project_service import analyze_project, build_project_intake
from backend.services.project_intelligence_service import build_feasibility_report, build_project_pipeline, discover_projects, read_project_library
from backend.services.report_service import dashboard_summary, read_text_report
from backend.services.search_service import multi_source_search
from backend.services.self_improvement_service import (
    build_self_improvement_plan,
    read_self_improvement_state,
    run_self_improvement_cycle,
)
from backend.services.social_communication_service import assess_social_context, build_authorized_social_reply
from backend.services.team_execution_service import build_team_execution_package
from backend.services.team_response_service import build_team_response_pack
from backend.services.war_room_execution_queue_service import read_latest_war_room_execution_queue
from backend.comm.chat_gateway import build_chat_reply_draft, save_chat_reply_draft, send_approved_webhook_message
from backend.integrations.n8n_connector import N8NConnector
from backend.workflows.system_integrity import run_integrity_check


async def offload(fn, *args, **kwargs):
    """把同步阻塞服务调用移出事件循环，避免单个慢请求卡死整个 API。"""
    return await asyncio.to_thread(fn, *args, **kwargs)


# ── v12 New Modules ──
from backend.api.matching_routes import router as matching_router
from backend.api.supply_chain_routes import router as supply_chain_router
from backend.api.financial_routes import router as financial_router
from backend.api.kg_routes import router as kg_router
from backend.api.bi_routes import router as bi_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Global Intelligence v12",
    version="12.0.0",
    description="International Engineering Trade Cloud OS — full-stack AI-powered platform for cross-border B2B trade.",
)

@app.on_event("startup")
async def _warm_core_retrieval():
    """Warm the multilingual embedding model in a dedicated thread at startup."""
    import threading
    threading.Thread(target=core_retrieval_service.warmup, daemon=True, name="core-warmup").start()


app.include_router(matching_router)
app.include_router(supply_chain_router)
app.include_router(financial_router)
app.include_router(kg_router)
app.include_router(bi_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

config = {
    "SECRET_KEY": "runtime-secret-required-in-production",
    "MAX_REQUESTS_PER_MINUTE": 100,
}

agent_pool = AgentPool()
orchestration_engine = OrchestrationEngine(config)
tenant_manager = TenantIsolationManager(config)

for agent_type, agent in agent_pool.get_all_agents().items():
    orchestration_engine.register_agent(agent_type, agent)


def _verify_tenant(org_id: str, user_id: str) -> bool:
    if not org_id or not user_id:
        return False
    return True


def _require_core_allowed() -> None:
    if not core_allowed():
        raise HTTPException(status_code=403, detail=license_status())


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except Exception:
        body = {}
    return body if isinstance(body, dict) else {}


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.time() - start_time)
    return response


@app.get("/v1/health")
async def health_check() -> dict[str, Any]:
    return {
        "status": "healthy",
        "version": "12.0.0",
        "architecture": "v12-full-stack",
        "agents": agent_pool.health_check(),
        "license": license_status(),
    }


@app.post("/v1/query")
async def query(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    org_id = str(body.get("org_id") or "owner")
    user_id = str(body.get("user_id") or "local-user")
    query_text = str(body.get("query") or body.get("q") or "").strip()
    metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}

    if not query_text:
        raise HTTPException(status_code=400, detail="query is required")
    if not _verify_tenant(org_id, user_id):
        raise HTTPException(status_code=403, detail="Unauthorized")

    orchestration = await orchestration_engine.execute_query(
        query=query_text,
        org_id=org_id,
        user_id=user_id,
        metadata=metadata,
    )
    team_response = await offload(
        build_team_response_pack,
        query_text,
        metadata=metadata,
        evidence=body.get("evidence") if isinstance(body.get("evidence"), list) else [],
        persist=True,
    )
    return {
        "execution_id": orchestration.get("execution_id"),
        "status": orchestration.get("status"),
        "mode": "team_response_pack",
        "team_response": team_response,
        "orchestration": orchestration,
    }


@app.post("/v1/search")
async def search(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    query_text = str(body.get("query") or body.get("q") or "").strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="query is required")
    return await offload(multi_source_search, query_text)


@app.post("/v1/intelligence/search-system")
async def intelligence_search_system(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    topics = body.get("topics") or body.get("topic") or body.get("query") or "international engineering trade"
    countries = body.get("countries") or body.get("country") or ["Kazakhstan", "Central Asia"]
    industries = body.get("industries") or body.get("industry") or ["infrastructure", "mining", "logistics", "energy"]
    return await offload(build_intelligence_search_system, topics, countries, industries)


@app.post("/v1/intelligence/brief")
async def intelligence_brief(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    topics = body.get("topics") or body.get("topic") or body.get("query") or "international engineering trade"
    countries = body.get("countries") or body.get("country") or ["Kazakhstan", "Central Asia"]
    industries = body.get("industries") or body.get("industry") or ["infrastructure", "mining", "logistics", "energy"]
    items = body.get("items") if isinstance(body.get("items"), list) else []
    return await offload(generate_intelligence_brief, topics, countries, industries, items)


@app.post("/v1/war-room/build")
async def war_room_build(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    objective = str(body.get("objective") or body.get("query") or body.get("topic") or "").strip()
    if not objective:
        raise HTTPException(status_code=400, detail="objective is required")
    return await offload(
        build_industry_war_room,
        objective,
        country=str(body.get("country") or "").strip() or None,
        industries=body.get("industries") or body.get("industry"),
        evidence=body.get("evidence") if isinstance(body.get("evidence"), list) else [],
        audience=str(body.get("audience") or "internal"),
        persist=True,
    )


@app.get("/v1/war-room/execution-queue")
async def war_room_execution_queue() -> dict[str, Any]:
    _require_core_allowed()
    return read_latest_war_room_execution_queue()


@app.get("/v1/intelligence/keywords")
async def intelligence_keywords() -> dict[str, Any]:
    _require_core_allowed()
    return read_keyword_bank()


@app.post("/v1/knowledge/build")
async def knowledge_build() -> dict[str, Any]:
    _require_core_allowed()
    return await offload(build_industry_knowledge_base)


@app.post("/v1/knowledge/query")
async def knowledge_query(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    query_text = str(body.get("query") or "").strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="query is required")
    try:
        n = int(body.get("n", 5))
    except (TypeError, ValueError):
        n = 5
    return await offload(knowledge_ingest_service.query, query_text, n=n)


@app.post("/v1/core/query")
async def core_query(request: Request) -> dict[str, Any]:
    """Two-stage retrieval over curated kb-core with reranking (+ legacy fallback)."""
    _require_core_allowed()
    body = await _json_body(request)
    query_text = str(body.get("query") or "").strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="query is required")
    try:
        n = int(body.get("n", 5))
    except (TypeError, ValueError):
        n = 5
    return await offload(core_retrieval_service.retrieve, query_text, n=n)


@app.post("/v1/benchmark/build")
async def benchmark_build() -> dict[str, Any]:
    _require_core_allowed()
    return await offload(build_v11_benchmark)


@app.post("/v1/answers/score")
async def answer_score(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    question = str(body.get("question") or "").strip()
    answer = str(body.get("answer") or "").strip()
    evidence = body.get("evidence") if isinstance(body.get("evidence"), list) else []
    if not question or not answer:
        raise HTTPException(status_code=400, detail="question and answer are required")
    return await offload(score_answer, question, answer, evidence=evidence)


@app.post("/v1/benchmark/compare")
async def benchmark_compare(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    question = str(body.get("question") or "").strip()
    answers = body.get("answers") if isinstance(body.get("answers"), dict) else {}
    if not question or not answers:
        raise HTTPException(status_code=400, detail="question and answers are required")
    return await offload(compare_answers, question, {str(key): str(value) for key, value in answers.items()})


@app.post("/v1/video/center")
async def video_center(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    topics = body.get("topics") or body.get("topic") or body.get("query") or "engineering trade project"
    countries = body.get("countries") or body.get("country") or ["Kazakhstan"]
    industries = body.get("industries") or body.get("industry") or ["infrastructure"]
    return await offload(build_video_production_center, topics, countries, industries)


@app.post("/v1/projects/intake")
async def project_intake(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    project = await offload(build_project_intake, body)
    return {
        "ok": True,
        "project": project.__dict__,
        "status": "draft_intake",
        "note": "Project intake is stored or escalated by workflow jobs; this endpoint does not send external commitments.",
    }


@app.post("/v1/projects/analyze")
async def project_analyze(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    return await offload(analyze_project, body)


@app.post("/v1/projects/discover")
async def project_discover(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    topic = str(body.get("topic") or body.get("query") or body.get("q") or "").strip()
    country = str(body.get("country") or "Kazakhstan").strip()
    evidence_items = body.get("evidence") if isinstance(body.get("evidence"), list) else []
    if not topic:
        raise HTTPException(status_code=400, detail="topic or query is required")
    return await offload(discover_projects, topic, country, evidence_items)


@app.post("/v1/projects/pipeline")
async def project_pipeline(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    topic = str(body.get("topic") or body.get("query") or body.get("q") or "").strip()
    country = str(body.get("country") or "Kazakhstan").strip()
    evidence_items = body.get("evidence") if isinstance(body.get("evidence"), list) else []
    if not topic:
        raise HTTPException(status_code=400, detail="topic or query is required")
    return await offload(build_project_pipeline, topic, country, evidence_items, persist=True)


@app.post("/v1/evidence/verify")
async def evidence_verify(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    claim = str(body.get("claim") or body.get("query") or body.get("topic") or "").strip()
    if not claim:
        raise HTTPException(status_code=400, detail="claim is required")
    evidence = body.get("evidence") if isinstance(body.get("evidence"), list) else []
    return await offload(
        verify_claim,
        claim,
        evidence,
        project=str(body.get("project") or ""),
        country=str(body.get("country") or "Kazakhstan"),
        persist=True,
    )


@app.post("/v1/projects/action-board")
async def project_action_board(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    case = body.get("case") if isinstance(body.get("case"), dict) else body
    evidence = body.get("evidence_dossier") if isinstance(body.get("evidence_dossier"), dict) else None
    if not isinstance(case, dict) or not case.get("project"):
        raise HTTPException(status_code=400, detail="case with project is required")
    return await offload(build_and_write_action_board, case, evidence)


@app.post("/v1/team/execute")
async def team_execute(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    objective = str(body.get("objective") or body.get("query") or body.get("topic") or "").strip()
    if not objective:
        raise HTTPException(status_code=400, detail="objective is required")
    return await offload(
        build_team_execution_package,
        objective,
        country=str(body.get("country") or "Kazakhstan"),
        industries=body.get("industries") or body.get("industry") or ["infrastructure", "mining", "logistics", "energy"],
        evidence=body.get("evidence") if isinstance(body.get("evidence"), list) else [],
        audience=str(body.get("audience") or "internal"),
    )


@app.post("/v1/team/response")
async def team_response(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    question = str(body.get("question") or body.get("query") or body.get("topic") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    return await offload(
        build_team_response_pack,
        question,
        metadata=body.get("metadata") if isinstance(body.get("metadata"), dict) else body,
        evidence=body.get("evidence") if isinstance(body.get("evidence"), list) else [],
        persist=True,
    )


@app.get("/v1/projects/library")
async def project_library() -> dict[str, Any]:
    _require_core_allowed()
    return await offload(read_project_library)


@app.get("/v1/reports/headquarters")
async def headquarters_report() -> dict[str, Any]:
    return await offload(read_text_report, "reports/headquarters_status.md")


@app.get("/v1/reports/owner-inbox")
async def owner_inbox() -> dict[str, Any]:
    return await offload(read_text_report, "reports/owner_inbox.md")


@app.post("/v1/reports/feasibility")
async def feasibility_report(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    project = body.get("project") if isinstance(body.get("project"), dict) else body
    if not project.get("title") and not project.get("topic"):
        raise HTTPException(status_code=400, detail="project title or topic is required")
    return await offload(build_feasibility_report, project)


@app.get("/v1/dashboard")
async def dashboard() -> dict[str, Any]:
    return await offload(dashboard_summary)


@app.get("/v1/mission-control")
async def mission_control() -> dict[str, Any]:
    _require_core_allowed()
    return await offload(write_mission_control)


@app.get("/v1/cloud/status")
async def get_cloud_status() -> dict[str, Any]:
    return await offload(cloud_status)


@app.post("/v1/cloud/check")
async def post_cloud_check() -> dict[str, Any]:
    _require_core_allowed()
    return await offload(cloud_check)


@app.post("/v1/cloud/run")
async def post_cloud_run() -> dict[str, Any]:
    _require_core_allowed()
    return await offload(cloud_run_requested)


@app.get("/v1/license/status")
async def get_license_status() -> dict[str, Any]:
    return await offload(license_status)


@app.post("/v1/license/refresh")
async def refresh_license() -> dict[str, Any]:
    return await offload(license_status)


@app.post("/v1/approvals/decision")
async def approval_decision(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    decision = str(body.get("decision") or "").strip().lower()
    if decision not in {"approve", "reject", "revise", "/approve", "/reject", "/revise"}:
        raise HTTPException(status_code=400, detail="decision must be approve, reject, or revise")
    clean_decision = decision.removeprefix("/")
    project = str(body.get("project") or "Unknown")
    verified = False
    approver = "unverified"
    if os.getenv("CLOUD_OS_APPROVAL_SECRET"):
        from backend.security.approval_gate import ApprovalGate
        gate = ApprovalGate()
        payload = gate.verify(
            str(body.get("approval_token") or ""),
            action="approval_decision",
            project=project,
        )
        if not payload or payload.get("decision") != clean_decision:
            raise HTTPException(status_code=403, detail="valid signed approval_token required")
        verified = True
        approver = str(payload.get("approver") or "unknown")
    from backend.services.audit_service import append_audit
    append_audit(
        "OWNER_DECISION",
        "DONE",
        f"decision={clean_decision} project={project} verifier={approver}",
        role="Owner" if verified else "Codex",
        risk="HIGH",
    )
    from backend.services.approval_receipt_service import issue_receipt
    receipt = issue_receipt(project, clean_decision, approver, verified=verified, note=str(body.get("note") or ""))
    return {
        "ok": True,
        "status": "recorded_for_workflow",
        "decision": clean_decision,
        "project": project,
        "note": body.get("note", ""),
        "verified": verified,
        "approver": approver,
        "receipt": receipt,
    }


@app.post("/v1/notifications/test")
async def notification_test(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    return {
        "ok": True,
        "status": "draft_only",
        "ticket": body,
        "note": "Notification adapters only send approval requests when runtime webhook/email secrets are configured.",
    }


@app.post("/v1/chat/reply-draft")
async def chat_reply_draft(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    draft = await offload(
        build_chat_reply_draft,
        channel=str(body.get("channel") or "wechat"),
        recipient=str(body.get("recipient") or "owner"),
        message=str(body.get("message") or ""),
        context=body.get("context") if isinstance(body.get("context"), dict) else {},
    )
    path = await offload(save_chat_reply_draft, draft)
    return {"ok": True, "sent": False, "draft": draft, "path": str(path), "reason": "human approval required"}


@app.post("/v1/chat/send-approved")
async def chat_send_approved(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    return await offload(send_approved_webhook_message, body)


@app.post("/v1/social/analyze")
async def social_analyze(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    return await offload(
        assess_social_context,
        channel=str(body.get("channel") or "wechat"),
        message=str(body.get("message") or body.get("inbound_message") or ""),
        authorization=body.get("authorization") if isinstance(body.get("authorization"), dict) else {},
        evidence=body.get("evidence") if isinstance(body.get("evidence"), list) else [],
        audience=str(body.get("audience") or "external"),
    )


@app.post("/v1/social/reply-draft")
async def social_reply_draft(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    return await offload(
        build_authorized_social_reply,
        channel=str(body.get("channel") or "wechat"),
        recipient=str(body.get("recipient") or "owner"),
        inbound_message=str(body.get("message") or body.get("inbound_message") or ""),
        authorization=body.get("authorization") if isinstance(body.get("authorization"), dict) else {},
        evidence=body.get("evidence") if isinstance(body.get("evidence"), list) else [],
        audience=str(body.get("audience") or "external"),
    )


@app.post("/v1/integrations/n8n/trigger/{workflow_id}")
async def trigger_n8n(workflow_id: str, request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    result = await offload(
        N8NConnector().trigger_workflow, workflow_id, body, str(body.get("org_id") or "owner")
    )
    return {"ok": result.get("status") == "success", "workflow_id": workflow_id, "result": result}


@app.post("/v1/system/integrity")
async def system_integrity() -> dict[str, Any]:
    _require_core_allowed()
    return await offload(run_integrity_check, auto_fix=True)


@app.get("/v1/system/self-improvement")
async def self_improvement_state() -> dict[str, Any]:
    _require_core_allowed()
    return await offload(read_self_improvement_state)


@app.post("/v1/system/self-improvement/plan")
async def self_improvement_plan(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    evidence = body.get("evidence") if isinstance(body.get("evidence"), dict) else body
    return await offload(build_self_improvement_plan, evidence)


@app.post("/v1/system/self-improvement/run")
async def self_improvement_run(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    evidence = body.get("evidence") if isinstance(body.get("evidence"), dict) else body
    return await offload(run_self_improvement_cycle, evidence)


@app.get("/v1/insights/{execution_id}")
async def get_insight(execution_id: str, org_id: str = "owner") -> dict[str, Any]:
    return {
        "execution_id": execution_id,
        "org_id": org_id,
        "status": "available",
        "dashboard": dashboard_summary(),
    }


@app.post("/v1/events/publish")
async def publish_event(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    event_type = str(body.get("event_type") or body.get("type") or "").strip()
    if not event_type:
        raise HTTPException(status_code=400, detail="event_type is required")
    from backend.services.event_bus import publish
    return publish(event_type, body.get("payload") if isinstance(body.get("payload"), dict) else {})


@app.get("/v1/events")
async def list_events(event_type: str | None = None, limit: int = 50) -> dict[str, Any]:
    from backend.services.event_bus import list_events as _list
    return {"ok": True, "events": _list(event_type, limit)}


@app.post("/v1/agents/debate")
async def agent_debate(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    claim = str(body.get("claim") or "").strip()
    if not claim:
        raise HTTPException(status_code=400, detail="claim is required")
    from backend.services.agent_debate_service import debate
    evidence = body.get("evidence") if isinstance(body.get("evidence"), list) else []
    return debate(claim, [str(e) for e in evidence], str(body.get("risk") or "medium"))


@app.post("/v1/learning/outcome")
async def record_outcome(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    project = str(body.get("project") or "").strip()
    if not project:
        raise HTTPException(status_code=400, detail="project is required")
    from backend.services.learning_loop_service import record_outcome as _record
    return _record(project, str(body.get("decision") or ""), str(body.get("outcome") or ""),
                   correct=body.get("correct"), score=float(body.get("score") or 0),
                   note=str(body.get("note") or ""))


@app.get("/v1/learning/report")
async def learning_report() -> dict[str, Any]:
    from backend.services.learning_loop_service import report as _report
    return _report()


@app.get("/v1/approvals/receipts")
async def approval_receipts(limit: int = 50) -> dict[str, Any]:
    from backend.services.approval_receipt_service import list_receipts
    return {"ok": True, "receipts": list_receipts(limit)}


@app.get("/v1/approvals/receipt/{receipt_id}")
async def verify_approval_receipt(receipt_id: str) -> dict[str, Any]:
    from backend.services.approval_receipt_service import verify_receipt
    return verify_receipt(receipt_id)


@app.post("/v1/alerts/send")
async def send_alert(request: Request) -> dict[str, Any]:
    _require_core_allowed()
    body = await _json_body(request)
    title = str(body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    from backend.services.alert_service import send
    return send(title, str(body.get("message") or ""), severity=str(body.get("severity") or "info"),
                source=str(body.get("source") or "api"))


@app.get("/v1/alerts")
async def list_alerts(limit: int = 50) -> dict[str, Any]:
    from backend.services.alert_service import alerts
    return {"ok": True, "alerts": alerts(limit)}


@app.post("/v1/knowledge/benchmark")
async def knowledge_benchmark(n: int = 5) -> dict[str, Any]:
    _require_core_allowed()
    from backend.services.rag_benchmark_service import evaluate
    return evaluate(n)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
