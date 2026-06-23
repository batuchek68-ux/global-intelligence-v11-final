from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.project_intelligence_service import assess_promotion_readiness, read_project_library
from backend.services.search_service import multi_source_search
from backend.services.industry_war_room_service import build_industry_war_room

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_JSON_RELATIVE = "reports/cloud_acceptance.json"
ACCEPTANCE_MD_RELATIVE = "reports/cloud_acceptance.md"
ACCEPTANCE_JSON = ROOT / ACCEPTANCE_JSON_RELATIVE
ACCEPTANCE_MD = ROOT / ACCEPTANCE_MD_RELATIVE


def read_text(relative: str) -> str:
    path = ROOT / relative
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_json(relative: str, default: dict | None = None) -> dict:
    path = ROOT / relative
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))


def check_file(relative: str) -> dict:
    path = ROOT / relative
    return {
        "name": f"file:{relative}",
        "ok": path.is_file(),
        "evidence": relative if path.is_file() else "missing",
    }


def check_text(relative: str, needle: str) -> dict:
    text = read_text(relative)
    return {
        "name": f"text:{relative}:{needle}",
        "ok": needle in text,
        "evidence": relative if needle in text else f"missing text: {needle}",
    }


def check_json_field(relative: str, name: str, predicate, evidence_value) -> dict:
    data = read_json(relative)
    evidence = evidence_value(data)
    return {
        "name": name,
        "ok": predicate(data),
        "evidence": evidence,
    }


def build_acceptance_status() -> dict:
    summary = read_json("memory/last_run.json")
    cases = summary.get("cases", [])
    capabilities = summary.get("v11_capabilities", {})
    knowledge = read_json("memory/knowledge_base/industry_knowledge.json")
    benchmark = read_json("memory/benchmark/v11_benchmark_50.json")
    answer_score = read_json("reports/benchmark/daily_answer_score.json")
    latest_evidence = read_json("memory/evidence/latest.json")
    latest_action_board = read_json("memory/action_boards/latest.json")
    latest_team_response = read_json("memory/team_responses/latest.json")
    latest_war_room = read_json("memory/war_room/latest.json")
    latest_war_room_queue = read_json("memory/war_room_execution/latest.json")
    keyword_bank = read_json("memory/intelligence/keyword_bank.json")
    mission_control = read_json("memory/mission_control/latest.json")
    search_gate_sample = multi_source_search("Kazakhstan engineering trade customs investment promotion video")
    source_readiness = search_gate_sample.get("source_readiness", {})
    project_confirmation_gate = search_gate_sample.get("project_confirmation_gate", {})
    project_library = read_project_library(ROOT / "memory" / "project_library" / "projects.json")
    project_library_summary = project_library.get("summary", {})
    war_room_sample = build_industry_war_room(
        "Kazakhstan engineering trade project customs investment promotion video",
        country="Kazakhstan",
        industries=["infrastructure", "logistics"],
        evidence=[],
        persist=False,
    ).get("war_room", {})
    weak_promotion_gate = assess_promotion_readiness(
        {
            "confirmation_level": "unverified_or_secondary",
            "confidence": 55,
            "category": "unknown",
            "government_sources": [],
            "owner_candidates": [],
            "developer_candidates": [],
        }
    )
    official_promotion_gate = assess_promotion_readiness(
        {
            "confirmation_level": "government_confirmed",
            "confidence": 95,
            "category": "planned",
            "government_sources": [{"url": "https://www.gov.kz/demo"}],
            "owner_candidates": ["Official owner candidate"],
            "developer_candidates": ["Official developer candidate"],
        }
    )
    execution_logs = sorted((ROOT / "memory" / "execution_logs").glob("*.json"))
    team_reports = sorted((ROOT / "reports" / "team_execution").glob("*.md"))
    team_memory = sorted((ROOT / "memory" / "team_execution").glob("*.json"))
    evidence_memory = sorted((ROOT / "memory" / "evidence").glob("*.json")) if (ROOT / "memory" / "evidence").is_dir() else []
    evidence_reports = sorted((ROOT / "reports" / "evidence").glob("*.md")) if (ROOT / "reports" / "evidence").is_dir() else []
    action_memory = sorted((ROOT / "memory" / "action_boards").glob("*.json")) if (ROOT / "memory" / "action_boards").is_dir() else []
    action_reports = sorted((ROOT / "reports" / "action_boards").glob("*.md")) if (ROOT / "reports" / "action_boards").is_dir() else []
    team_response_memory = sorted((ROOT / "memory" / "team_responses").glob("*.json")) if (ROOT / "memory" / "team_responses").is_dir() else []
    team_response_reports = sorted((ROOT / "reports" / "team_responses").glob("*.md")) if (ROOT / "reports" / "team_responses").is_dir() else []
    war_room_memory = sorted((ROOT / "memory" / "war_room").glob("*.json")) if (ROOT / "memory" / "war_room").is_dir() else []
    war_room_reports = sorted((ROOT / "reports" / "war_room").glob("*.md")) if (ROOT / "reports" / "war_room").is_dir() else []
    war_room_queue_memory = sorted((ROOT / "memory" / "war_room_execution").glob("*.json")) if (ROOT / "memory" / "war_room_execution").is_dir() else []
    war_room_queue_reports = sorted((ROOT / "reports" / "war_room_execution").glob("*.md")) if (ROOT / "reports" / "war_room_execution").is_dir() else []
    intelligence_briefs = sorted((ROOT / "reports" / "intelligence_briefs").glob("*.md"))
    video_center_files = sorted((ROOT / "reports" / "video_center").glob("*.json"))
    waiting_for_owner = [
        case
        for case in cases
        if case.get("classification", {}).get("is_major_matter") and not case.get("owner_decision")
    ]
    autonomous_cases = [
        case
        for case in cases
        if not case.get("classification", {}).get("is_major_matter")
    ]
    resolved_major_matters = [case for case in cases if case.get("owner_decision")]

    checks = [
        check_file(".github/workflows/international_trade_ops.yml"),
        check_file(".github/workflows/owner_decision.yml"),
        check_file(".github/workflows/watchdog.yml"),
        check_file(".github/workflows/cloud_acceptance.yml"),
        check_file(".github/workflows/codex_autonomous_repair.yml"),
        check_file("reports/headquarters_status.md"),
        check_file("reports/owner_inbox.md"),
        check_file("reports/watchdog_status.md"),
        check_file("memory/last_run.json"),
        check_file("memory/knowledge_base/industry_knowledge.json"),
        check_file("memory/benchmark/v11_benchmark_50.json"),
        check_file("memory/evidence/latest.json"),
        check_file("reports/evidence/latest.md"),
        check_file("memory/action_boards/latest.json"),
        check_file("reports/action_boards/latest.md"),
        check_file("memory/team_responses/latest.json"),
        check_file("reports/team_responses/latest.md"),
        check_file("memory/war_room/latest.json"),
        check_file("reports/war_room/latest.md"),
        check_file("memory/war_room_execution/latest.json"),
        check_file("reports/war_room_execution/latest.md"),
        check_file("memory/intelligence/keyword_bank.json"),
        check_file("memory/mission_control/latest.json"),
        check_file("reports/mission_control/latest.md"),
        check_file("services/industry_war_room_service.py"),
        check_file("reports/benchmark/daily_answer_score.json"),
        check_text(".github/workflows/international_trade_ops.yml", "python workflows/daily_job.py"),
        check_text(".github/workflows/international_trade_ops.yml", "python workflows/persist_state.py"),
        check_text(".github/workflows/owner_decision.yml", "issue_comment"),
        check_text(".github/workflows/owner_decision.yml", "python workflows/resolve_major_matter.py"),
        check_text(".github/workflows/watchdog.yml", "python workflows/persist_state.py"),
        check_text(".github/workflows/cloud_acceptance.yml", "python workflows/cloud_acceptance.py"),
        check_text(".github/workflows/codex_autonomous_repair.yml", "python workflows/autonomous_repair.py"),
        check_text("reports/headquarters_status.md", "Execution status"),
        check_text("reports/owner_inbox.md", "Owner Inbox"),
        check_text("reports/watchdog_status.md", "24h Codex Watchdog"),
        {
            "name": "last_run:projects_scanned",
            "ok": summary.get("project_count", 0) > 0,
            "evidence": f"project_count={summary.get('project_count', 0)}",
        },
        {
            "name": "last_run:cases_created",
            "ok": summary.get("case_count", 0) == len(cases) and len(cases) > 0,
            "evidence": f"case_count={summary.get('case_count', 0)}, cases={len(cases)}",
        },
        {
            "name": "execution_logs:one_per_case",
            "ok": len(execution_logs) >= len(cases) > 0,
            "evidence": f"execution_logs={len(execution_logs)}, cases={len(cases)}",
        },
        {
            "name": "owner_boundary:major_matters_identified",
            "ok": summary.get("major_matter_count", 0) >= len(waiting_for_owner),
            "evidence": (
                f"major_matter_count={summary.get('major_matter_count', 0)}, "
                f"waiting_for_owner={len(waiting_for_owner)}"
            ),
        },
        {
            "name": "owner_boundary:resolved_or_waiting",
            "ok": summary.get("major_matter_count", 0) == len(waiting_for_owner) + len(resolved_major_matters),
            "evidence": (
                f"major={summary.get('major_matter_count', 0)}, "
                f"resolved={len(resolved_major_matters)}, waiting={len(waiting_for_owner)}"
            ),
        },
        {
            "name": "codex_autonomy:autonomous_cases_recorded",
            "ok": len(autonomous_cases) > 0,
            "evidence": f"autonomous_cases={len(autonomous_cases)}",
        },
        {
            "name": "real_work:business_flows_generated",
            "ok": (ROOT / "reports" / "business_flows").is_dir()
            and len(list((ROOT / "reports" / "business_flows").glob("*.md"))) >= len(cases) > 0,
            "evidence": f"business_flow_reports={len(list((ROOT / 'reports' / 'business_flows').glob('*.md'))) if (ROOT / 'reports' / 'business_flows').is_dir() else 0}",
        },
        {
            "name": "v11_knowledge:domains_and_customs",
            "ok": "customs_information" in knowledge.get("domains", {}) and len(knowledge.get("domains", {})) >= 7,
            "evidence": f"domains={len(knowledge.get('domains', {}))}, customs={'customs_information' in knowledge.get('domains', {})}",
        },
        {
            "name": "v11_benchmark:50_questions",
            "ok": benchmark.get("question_count", 0) >= 50
            and {"v11", "Doubao", "Yuanbao"}.issubset(
                set(benchmark.get("questions", [{}])[0].get("compare_targets", [])) if benchmark.get("questions") else set()
            ),
            "evidence": f"question_count={benchmark.get('question_count', 0)}",
        },
        {
            "name": "v11_answer_scorer:daily_quality_score",
            "ok": answer_score.get("overall_score", 0) >= 70
            and all(
                key in answer_score.get("dimensions", {})
                for key in ["accuracy", "evidence", "actionability", "risk_judgment", "professional_depth"]
            ),
            "evidence": f"overall_score={answer_score.get('overall_score', 0)}, verdict={answer_score.get('verdict', 'missing')}",
        },
        {
            "name": "v11_intelligence:keyword_bank_and_brief",
            "ok": len(keyword_bank.get("keywords", [])) > 0 and len(intelligence_briefs) > 0,
            "evidence": f"keywords={len(keyword_bank.get('keywords', []))}, briefs={len(intelligence_briefs)}",
        },
        {
            "name": "v11_video:center_generated",
            "ok": len(video_center_files) > 0
            and capabilities.get("video_center", {}).get("platform_search_count", 0) > 0,
            "evidence": (
                f"video_files={len(video_center_files)}, "
                f"platform_searches={capabilities.get('video_center', {}).get('platform_search_count', 0)}"
            ),
        },
        {
            "name": "v11_team_execution:packages_generated",
            "ok": len(team_reports) >= len(cases) > 0 and len(team_memory) >= len(cases) > 0,
            "evidence": f"team_reports={len(team_reports)}, team_memory={len(team_memory)}, cases={len(cases)}",
        },
        {
            "name": "v11_evidence:verification_dossiers",
            "ok": len([item for item in evidence_memory if item.name != "latest.json"]) >= len(cases) > 0
            and len([item for item in evidence_reports if item.name != "latest.md"]) >= len(cases) > 0
            and latest_evidence.get("verification_status") in {"officially_supported", "partially_supported", "weak_signal_only", "unverified"},
            "evidence": (
                f"evidence_json={len(evidence_memory)}, evidence_reports={len(evidence_reports)}, "
                f"latest_status={latest_evidence.get('verification_status', 'missing')}"
            ),
        },
        {
            "name": "v11_action_board:execution_tasks",
            "ok": len([item for item in action_memory if item.name != "latest.json"]) >= len(cases) > 0
            and len([item for item in action_reports if item.name != "latest.md"]) >= len(cases) > 0
            and latest_action_board.get("summary", {}).get("task_count", 0) >= 6,
            "evidence": (
                f"action_json={len(action_memory)}, action_reports={len(action_reports)}, "
                f"latest_tasks={latest_action_board.get('summary', {}).get('task_count', 0)}, "
                f"latest_status={latest_action_board.get('risk_gate', {}).get('status', 'missing')}"
            ),
        },
        {
            "name": "v11_team_response:team_answer_pack",
            "ok": len([item for item in team_response_memory if item.name != "latest.json"]) > 0
            and len([item for item in team_response_reports if item.name != "latest.md"]) > 0
            and latest_team_response.get("mode") == "team_response_pack"
            and latest_team_response.get("quality_score", {}).get("overall_score", 0) >= 70
            and len(latest_team_response.get("team_roles", [])) >= 6,
            "evidence": (
                f"team_response_json={len(team_response_memory)}, "
                f"score={latest_team_response.get('quality_score', {}).get('overall_score', 0)}, "
                f"roles={len(latest_team_response.get('team_roles', []))}"
            ),
        },
        {
            "name": "v11_search:source_readiness_and_confirmation_gate",
            "ok": source_readiness.get("configured_count", 0) > 0
            and project_confirmation_gate.get("status") == "lead_only"
            and project_confirmation_gate.get("can_create_confirmed_project_record") is False
            and {"government_confirmation", "procurement_tender", "customs_trade"}.issubset(
                set(project_confirmation_gate.get("required_query_groups", {}).keys())
            )
            and len(project_confirmation_gate.get("blocked_until_confirmed", [])) >= 5,
            "evidence": (
                f"sources={source_readiness.get('configured_count', 0)}, "
                f"manual={source_readiness.get('manual_entry_count', 0)}, "
                f"gate={project_confirmation_gate.get('status', 'missing')}, "
                f"required={','.join(sorted(project_confirmation_gate.get('required_query_groups', {}).keys()))}, "
                f"blocked={len(project_confirmation_gate.get('blocked_until_confirmed', []))}"
            ),
        },
        {
            "name": "v11_project:promotion_readiness_gate",
            "ok": weak_promotion_gate.get("status") == "lead_only"
            and official_promotion_gate.get("status") == "draft_promotion_ready"
            and official_promotion_gate.get("can_generate_internal_promotion_draft") is True
            and official_promotion_gate.get("approved_for_external_use") is False
            and official_promotion_gate.get("human_approval_required_for_external_use") is True
            and "正式招商发布" in official_promotion_gate.get("blocked_actions", []),
            "evidence": (
                f"weak={weak_promotion_gate.get('status')}, "
                f"official={official_promotion_gate.get('status')}, "
                f"external={official_promotion_gate.get('approved_for_external_use')}, "
                f"library_total={project_library_summary.get('total', 0)}, "
                f"draft_ready={project_library_summary.get('promotion_draft_ready', 0)}, "
                f"lead_only={project_library_summary.get('lead_only', 0)}"
            ),
        },
        {
            "name": "v11_war_room:vertical_team_operating_package",
            "ok": war_room_sample.get("mode") == "industry_war_room"
            and latest_war_room.get("mode") == "industry_war_room"
            and war_room_sample.get("search_confirmation", {}).get("project_confirmation_gate", {}).get("status") == "lead_only"
            and war_room_sample.get("project_execution", {}).get("promotion_readiness", {}).get("status") == "lead_only"
            and len(war_room_sample.get("team", {}).get("roles", [])) >= 6
            and len(war_room_sample.get("video_center", {}).get("platform_searches", [])) > 0
            and war_room_sample.get("approval_boundary", {}).get("external_use_allowed") is False
            and war_room_sample.get("quality_score", {}).get("overall_score", 0) >= 70,
            "evidence": (
                f"latest={latest_war_room.get('mode')}, "
                f"saved_json={len([item for item in war_room_memory if item.name != 'latest.json'])}, "
                f"saved_reports={len([item for item in war_room_reports if item.name != 'latest.md'])}, "
                f"mode={war_room_sample.get('mode')}, "
                f"search_gate={war_room_sample.get('search_confirmation', {}).get('project_confirmation_gate', {}).get('status')}, "
                f"promotion={war_room_sample.get('project_execution', {}).get('promotion_readiness', {}).get('status')}, "
                f"roles={len(war_room_sample.get('team', {}).get('roles', []))}, "
                f"video={len(war_room_sample.get('video_center', {}).get('platform_searches', []))}, "
                f"score={war_room_sample.get('quality_score', {}).get('overall_score', 0)}"
            ),
        },
        {
            "name": "v11_war_room_execution:queue_tracks_work",
            "ok": len([item for item in war_room_queue_memory if item.name != "latest.json"]) > 0
            and len([item for item in war_room_queue_reports if item.name != "latest.md"]) > 0
            and latest_war_room_queue.get("mode") == "war_room_execution_queue"
            and latest_war_room_queue.get("summary", {}).get("task_count", 0) >= 12
            and latest_war_room_queue.get("summary", {}).get("blocked_count", 0) > 0
            and latest_war_room_queue.get("summary", {}).get("approval_required_count", 0) > 0
            and any(item.get("source", "").startswith("search_confirmation") for item in latest_war_room_queue.get("tasks", []))
            and any(item.get("role") == "video_media_producer" for item in latest_war_room_queue.get("tasks", [])),
            "evidence": (
                f"queues={len([item for item in war_room_queue_memory if item.name != 'latest.json'])}, "
                f"reports={len([item for item in war_room_queue_reports if item.name != 'latest.md'])}, "
                f"mode={latest_war_room_queue.get('mode', 'missing')}, "
                f"tasks={latest_war_room_queue.get('summary', {}).get('task_count', 0)}, "
                f"open={latest_war_room_queue.get('summary', {}).get('open_count', 0)}, "
                f"blocked={latest_war_room_queue.get('summary', {}).get('blocked_count', 0)}, "
                f"approval={latest_war_room_queue.get('summary', {}).get('approval_required_count', 0)}"
            ),
        },
        {
            "name": "v11_mission_control:operating_brief",
            "ok": mission_control.get("ok") is True
            and mission_control.get("capability_evidence", {}).get("customs_information_domain") is True
            and mission_control.get("capability_evidence", {}).get("benchmark_questions", 0) >= 50
            and mission_control.get("capability_evidence", {}).get("evidence_dossiers", 0) >= len(cases)
            and mission_control.get("capability_evidence", {}).get("action_boards", 0) >= len(cases)
            and mission_control.get("capability_evidence", {}).get("team_responses", 0) > 0
            and mission_control.get("capability_evidence", {}).get("war_rooms", 0) > 0
            and mission_control.get("capability_evidence", {}).get("war_room_execution_queues", 0) > 0
            and mission_control.get("capability_evidence", {}).get("latest_war_room_queue_tasks", 0) >= 12
            and mission_control.get("capability_evidence", {}).get("latest_war_room_mode") == "industry_war_room"
            and mission_control.get("capability_evidence", {}).get("latest_war_room_score", 0) >= 70
            and mission_control.get("capability_evidence", {}).get("search_confirmation_gate", {}).get("status") == "lead_only"
            and mission_control.get("capability_evidence", {}).get("promotion_readiness_gate", {}).get("weak_lead_status") == "lead_only"
            and mission_control.get("capability_evidence", {}).get("promotion_readiness_gate", {}).get("official_project_status") == "draft_promotion_ready"
            and (ROOT / "reports" / "mission_control" / "latest.md").is_file(),
            "evidence": (
                f"status={mission_control.get('status', 'missing')}, "
                f"benchmark={mission_control.get('capability_evidence', {}).get('benchmark_questions', 0)}, "
                f"customs={mission_control.get('capability_evidence', {}).get('customs_information_domain')}, "
                f"evidence={mission_control.get('capability_evidence', {}).get('evidence_dossiers', 0)}, "
                f"boards={mission_control.get('capability_evidence', {}).get('action_boards', 0)}, "
                f"responses={mission_control.get('capability_evidence', {}).get('team_responses', 0)}, "
                f"war_rooms={mission_control.get('capability_evidence', {}).get('war_rooms', 0)}, "
                f"queues={mission_control.get('capability_evidence', {}).get('war_room_execution_queues', 0)}, "
                f"queue_tasks={mission_control.get('capability_evidence', {}).get('latest_war_room_queue_tasks', 0)}, "
                f"war_score={mission_control.get('capability_evidence', {}).get('latest_war_room_score', 0)}, "
                f"search_gate={mission_control.get('capability_evidence', {}).get('search_confirmation_gate', {}).get('status', 'missing')}, "
                f"promotion_gate={mission_control.get('capability_evidence', {}).get('promotion_readiness_gate', {}).get('official_project_status', 'missing')}"
            ),
        },
    ]

    ok = all(check["ok"] for check in checks)
    return {
        "ok": ok,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repository": os.getenv("GITHUB_REPOSITORY", "local"),
        "run_id": os.getenv("GITHUB_RUN_ID", "local"),
        "command_model": {
            "github": "cloud AI headquarters",
            "codex": "24h autonomous executive",
            "owner": "decides only major matters",
        },
        "summary": {
            "projects": summary.get("project_count", 0),
            "cases": len(cases),
            "major_matters": summary.get("major_matter_count", 0),
            "resolved_major_matters": len(resolved_major_matters),
            "waiting_for_owner": len(waiting_for_owner),
            "autonomous_cases": len(autonomous_cases),
            "execution_logs": len(execution_logs),
            "knowledge_domains": len(knowledge.get("domains", {})),
            "customs_information_domain": "customs_information" in knowledge.get("domains", {}),
            "benchmark_questions": benchmark.get("question_count", 0),
            "answer_score": answer_score.get("overall_score", 0),
            "intelligence_keywords": len(keyword_bank.get("keywords", [])),
            "intelligence_briefs": len(intelligence_briefs),
            "video_center_files": len(video_center_files),
            "team_execution_reports": len(team_reports),
            "evidence_dossiers": len([item for item in evidence_memory if item.name != "latest.json"]),
            "latest_evidence_status": latest_evidence.get("verification_status", "missing"),
            "action_boards": len([item for item in action_memory if item.name != "latest.json"]),
            "latest_action_board_status": latest_action_board.get("risk_gate", {}).get("status", "missing"),
            "team_responses": len([item for item in team_response_memory if item.name != "latest.json"]),
            "latest_team_response_score": latest_team_response.get("quality_score", {}).get("overall_score", 0),
            "war_rooms": len([item for item in war_room_memory if item.name != "latest.json"]),
            "war_room_execution_queues": len([item for item in war_room_queue_memory if item.name != "latest.json"]),
            "latest_war_room_queue_tasks": latest_war_room_queue.get("summary", {}).get("task_count", 0),
            "latest_war_room_queue_blocked": latest_war_room_queue.get("summary", {}).get("blocked_count", 0),
            "latest_war_room_score": latest_war_room.get("quality_score", {}).get("overall_score", 0),
            "latest_war_room_mode": latest_war_room.get("mode", "missing"),
            "search_source_entries": source_readiness.get("configured_count", 0),
            "search_confirmation_gate": project_confirmation_gate.get("status", "missing"),
            "project_library_total": project_library_summary.get("total", 0),
            "promotion_draft_ready": project_library_summary.get("promotion_draft_ready", 0),
            "promotion_gate_weak_lead": weak_promotion_gate.get("status"),
            "promotion_gate_official_project": official_promotion_gate.get("status"),
            "war_room_score": war_room_sample.get("quality_score", {}).get("overall_score", 0),
            "war_room_roles": len(war_room_sample.get("team", {}).get("roles", [])),
            "mission_control_status": mission_control.get("status", "missing"),
        },
        "checks": checks,
    }


def render_acceptance_report(status: dict) -> str:
    lines = [
        "# GitHub Cloud Acceptance",
        "",
        f"- Status: {'PASS' if status.get('ok') else 'FAIL'}",
        f"- Generated: {status.get('created_at')}",
        f"- Repository: {status.get('repository')}",
        f"- Run id: {status.get('run_id')}",
        "",
        "## Command Model",
        "",
        "- GitHub = cloud AI headquarters",
        "- Codex = 24h autonomous executive",
        "- Owner = decides only major matters",
        "",
        "## Summary",
        "",
    ]
    for key, value in status.get("summary", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Checks", ""])
    for check in status.get("checks", []):
        mark = "PASS" if check.get("ok") else "FAIL"
        lines.append(f"- {mark} `{check.get('name')}` - {check.get('evidence')}")
    lines.append("")
    return "\n".join(lines)


def publish_to_step_summary(report: str) -> dict:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return {"published": False, "reason": "GITHUB_STEP_SUMMARY not configured"}
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write(report)
        handle.write("\n")
    return {"published": True, "summary_path": summary_path}


def run_acceptance() -> dict:
    status = build_acceptance_status()
    ACCEPTANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    ACCEPTANCE_JSON.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    report = render_acceptance_report(status)
    ACCEPTANCE_MD.write_text(report, encoding="utf-8")
    status["report_path"] = str(ACCEPTANCE_MD)
    status["json_path"] = str(ACCEPTANCE_JSON)
    status["publish"] = publish_to_step_summary(report)
    return status


def main() -> None:
    status = run_acceptance()
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if not status.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
