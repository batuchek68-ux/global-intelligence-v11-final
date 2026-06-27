from __future__ import annotations

import sys
import os
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from comm.notification import notify_major_matter
from comm.wechat import build_approval_ticket, merge_existing_ticket, write_outbox
from comm.github_issue import maybe_create_issue
from content.video_script import build_video_script
from core.business_flow import build_business_flow, render_business_flow
from core.executor import build_execution_record
from core.judge import judge_project
from core.models import OperatingCase, now_iso
from core.operator import build_operator_log, classify_matter
from core.planner import plan_actions
from core.project_loader import load_active_projects
from core.report import build_headquarters_report, build_owner_inbox
from core.storage import ensure_dirs, read_json, safe_slug, write_json, write_text
from intelligence.brief_generator import build_research_brief
from intelligence.kazakhstan_xinjiang_monitor import build_monitoring_summary
from backend.services.evidence_verification_service import verify_claim
from backend.services.industry_war_room_service import build_industry_war_room
from backend.services.intelligence_center_service import (
    build_video_production_center,
    generate_intelligence_brief,
)
from backend.services.knowledge_benchmark_service import (
    build_industry_knowledge_base,
    build_v11_benchmark,
    score_answer,
)
from backend.services.mission_control_service import write_mission_control
from backend.services.project_action_board_service import build_and_write_action_board
from backend.services.team_execution_service import build_team_execution_package
from backend.services.team_response_service import build_team_response_pack


@contextmanager
def v11_output_paths(root: Path):
    """Route v11 service artifacts to the active workflow root."""
    mapping = {
        "V11_KNOWLEDGE_BASE_PATH": root / "memory" / "knowledge_base" / "industry_knowledge.json",
        "V11_BENCHMARK_PATH": root / "memory" / "benchmark" / "v11_benchmark_50.json",
        "V11_EVIDENCE_MEMORY_DIR": root / "memory" / "evidence",
        "V11_EVIDENCE_REPORT_DIR": root / "reports" / "evidence",
        "V11_ACTION_BOARD_MEMORY_DIR": root / "memory" / "action_boards",
        "V11_ACTION_BOARD_REPORT_DIR": root / "reports" / "action_boards",
        "V11_KEYWORD_BANK_PATH": root / "memory" / "intelligence" / "keyword_bank.json",
        "V11_INTELLIGENCE_BRIEF_DIR": root / "reports" / "intelligence_briefs",
        "V11_VIDEO_CENTER_DIR": root / "reports" / "video_center",
        "V11_TEAM_EXECUTION_REPORT_DIR": root / "reports" / "team_execution",
        "V11_TEAM_EXECUTION_MEMORY_DIR": root / "memory" / "team_execution",
        "V11_TEAM_RESPONSE_MEMORY_DIR": root / "memory" / "team_responses",
        "V11_TEAM_RESPONSE_REPORT_DIR": root / "reports" / "team_responses",
        "V11_WAR_ROOM_MEMORY_DIR": root / "memory" / "war_room",
        "V11_WAR_ROOM_REPORT_DIR": root / "reports" / "war_room",
        "V11_WAR_ROOM_EXECUTION_MEMORY_DIR": root / "memory" / "war_room_execution",
        "V11_WAR_ROOM_EXECUTION_REPORT_DIR": root / "reports" / "war_room_execution",
        "V11_MISSION_CONTROL_DIR": root / "reports" / "mission_control",
        "V11_MISSION_CONTROL_MEMORY_DIR": root / "memory" / "mission_control",
    }
    previous = {key: os.environ.get(key) for key in mapping}
    try:
        for key, value in mapping.items():
            os.environ[key] = str(value)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_daily_cycle(projects: list | None = None) -> dict:
    with v11_output_paths(ROOT):
        return _run_daily_cycle(projects)


def _run_daily_cycle(projects: list | None = None) -> dict:
    ensure_dirs()
    projects = projects if projects is not None else load_active_projects()
    cases: list[dict] = []
    team_packages: list[dict] = []

    for project in projects:
        slug = safe_slug(project.title)
        judgment = judge_project(project)
        actions = plan_actions(project, judgment)

        brief = build_research_brief(project, judgment)
        video = build_video_script(project, judgment)
        business_flow = build_business_flow(project, judgment)
        brief_path = write_text(ROOT / "research" / "briefs" / f"{slug}.md", brief)
        video_path = write_text(ROOT / "media" / "drafts" / f"{slug}.md", video)
        business_flow_path = write_text(ROOT / "reports" / "business_flows" / f"{slug}.md", render_business_flow(business_flow))
        business_flow_json_path = write_json(ROOT / "reports" / "business_flows" / f"{slug}.json", business_flow)
        evidence_dossier = verify_claim(
            f"{project.title} project status, stakeholders, customs and trade risk",
            [
                {
                    "title": project.title,
                    "url": project.path,
                    "snippet": project.latest_communication,
                    "source_type": "internal",
                    "collected_at": now_iso(),
                }
            ],
            project=project.title,
            country=project.country if project.country != "Unknown" else "Kazakhstan",
            persist=True,
        )
        team_package = build_team_execution_package(
            f"{project.title} international engineering trade and intelligence execution",
            country=project.country if project.country != "Unknown" else "Kazakhstan",
            industries=["infrastructure", "mining", "logistics", "energy"],
            evidence=[
                {
                    "title": project.title,
                    "snippet": project.latest_communication,
                    "source_type": "internal",
                    "url": project.path,
                }
            ],
            audience="internal",
        )

        outbox_path = None
        notification_result = {
            "enterprise_wechat": {"sent": False, "reason": "approval not needed"},
            "feishu": {"sent": False, "reason": "approval not needed"},
            "email": {"sent": False, "reason": "approval not needed"},
        }
        github_issue_result = {"created": False, "reason": "approval not needed"}
        owner_decision = None
        if judgment.needs_approval:
            ticket = build_approval_ticket(project, judgment)
            outbox = ROOT / "comm" / "outbox" / f"{slug}.json"
            existing_ticket = read_json(outbox, None)
            ticket = merge_existing_ticket(ticket, existing_ticket)
            outbox_path = str(write_outbox(ticket, outbox))
            owner_decision = ticket.get("owner_decision")
            if ticket.get("status") == "resolved":
                notification_result = {
                    "enterprise_wechat": {"sent": False, "reason": "major matter already resolved"},
                    "feishu": {"sent": False, "reason": "major matter already resolved"},
                    "email": {"sent": False, "reason": "major matter already resolved"},
                }
                github_issue_result = {"created": False, "reason": "major matter already resolved"}
                actions.append(f"Continue according to owner decision: {owner_decision}.")
            elif existing_ticket and existing_ticket.get("status") == "waiting":
                notification_result = {
                    "enterprise_wechat": {"sent": False, "reason": "approval already waiting"},
                    "feishu": {"sent": False, "reason": "approval already waiting"},
                    "email": {"sent": False, "reason": "approval already waiting"},
                }
                github_issue_result = {"created": False, "reason": "approval already waiting"}
            else:
                notification_result = notify_major_matter(ticket)
                github_issue_result = maybe_create_issue(ticket)
                if github_issue_result.get("created"):
                    ticket["github_issue"] = github_issue_result
                    ticket["notifications"] = notification_result
                    write_outbox(ticket, outbox)

        classification = classify_matter(project, judgment)
        execution_record = build_execution_record(project, judgment, actions, classification, owner_decision)
        execution_log_path = write_json(ROOT / "memory" / "execution_logs" / f"{slug}.json", execution_record)

        operator_log = build_operator_log(project, judgment, actions)
        operator_log_path = write_text(ROOT / "memory" / "operator_logs" / f"{slug}.md", operator_log)

        case = OperatingCase(
            project=project,
            judgment=judgment,
            actions=actions,
            brief_path=str(brief_path),
            video_path=str(video_path),
            outbox_path=outbox_path,
        )
        case_data = case.to_dict()
        case_data["classification"] = classification
        case_data["business_flow"] = business_flow
        case_data["business_flow_path"] = str(business_flow_path)
        case_data["business_flow_json_path"] = str(business_flow_json_path)
        case_data["evidence_dossier_id"] = evidence_dossier["dossier"]["id"]
        case_data["team_execution_package_id"] = team_package["id"]
        case_data["execution"] = execution_record
        case_data["execution_log_path"] = str(execution_log_path)
        case_data["operator_log_path"] = str(operator_log_path)
        case_data["owner_decision"] = owner_decision
        case_data["notifications"] = notification_result
        case_data["webhook"] = notification_result.get("enterprise_wechat", {})
        case_data["github_issue"] = github_issue_result
        action_board = build_and_write_action_board(case_data, evidence_dossier["dossier"])
        case_data["action_board_id"] = action_board["board"]["id"]
        case_data["action_board_path"] = action_board["report_path"]
        write_json(ROOT / "memory" / "cases" / f"{slug}.json", case_data)
        cases.append(case_data)
        team_packages.append(
            {
                "id": team_package["id"],
                "objective": team_package["objective"],
                "risk": team_package["risk"],
                "deliverable_count": len(team_package["deliverables"]),
                "role_count": len(team_package["team_roles"]),
            }
        )

    topics = [project.title for project in projects] or ["Kazakhstan engineering trade"]
    countries = sorted({project.country for project in projects if project.country and project.country != "Unknown"}) or ["Kazakhstan"]
    industries = ["infrastructure", "mining", "logistics", "energy", "customs", "investment"]
    knowledge_base = build_industry_knowledge_base()
    benchmark = build_v11_benchmark()
    intelligence_brief = generate_intelligence_brief(topics, countries, industries)
    video_center = build_video_production_center(topics, countries, industries[:4])
    answer_scoring = score_answer(
        "How should v11 build a customs-backed project intelligence library?",
        (
            "Use official customs authority sources, HS code and tariff evidence, "
            "government project pages, actionable checklists, risk approval gates, "
            "and append-only audit records before any external commitment."
        ),
        evidence=[{"source_type": "official", "url": "official-source-required"}],
    )
    answer_score_path = write_json(ROOT / "reports" / "benchmark" / "daily_answer_score.json", answer_scoring)
    daily_team_response = build_team_response_pack(
        "How should v11 operate today as an international engineering trade, research intelligence, investment promotion, video, and project execution team?",
        metadata={"country": countries[0], "industries": industries, "project": "Daily v11 operating response"},
        evidence=[{"title": "Daily cycle evidence", "url": str(ROOT / "memory" / "last_run.json"), "source_type": "internal", "snippet": "daily operating cycle"}],
        persist=True,
    )
    daily_war_room = build_industry_war_room(
        "Daily v11 international engineering trade, research intelligence, investment promotion, video, customs, and project execution operating package",
        country=countries[0],
        industries=industries,
        evidence=[
            {
                "title": "Daily cycle operating evidence",
                "url": str(ROOT / "memory" / "last_run.json"),
                "source_type": "internal",
                "snippet": "daily operating cycle, project cases, evidence dossiers, action boards, video center, benchmark and owner approval queue",
            }
        ],
        audience="internal",
        persist=True,
    )

    monitoring_summary = build_monitoring_summary(ROOT)

    summary = {
        "created_at": now_iso(),
        "project_count": len(projects),
        "case_count": len(cases),
        "approval_count": sum(1 for item in cases if item["judgment"]["needs_approval"]),
        "major_matter_count": sum(1 for item in cases if item["classification"]["is_major_matter"]),
        "resolved_major_matter_count": sum(1 for item in cases if item.get("owner_decision")),
        "monitoring": monitoring_summary,
        "v11_capabilities": {
            "knowledge_base": {
                "path": knowledge_base["path"],
                "domain_count": len(knowledge_base["data"]["domains"]),
                "has_customs_information": "customs_information" in knowledge_base["data"]["domains"],
            },
            "benchmark": {
                "path": benchmark["path"],
                "question_count": benchmark["data"]["question_count"],
                "compare_targets": ["v11", "Doubao", "Yuanbao"],
            },
            "answer_scoring": {
                "path": str(answer_score_path),
                "overall_score": answer_scoring["overall_score"],
                "verdict": answer_scoring["verdict"],
            },
            "intelligence_brief": {
                "path": intelligence_brief["path"],
                "category_count": len(intelligence_brief["search_system"]["categories"]),
                "keyword_bank_path": str(ROOT / "memory" / "intelligence" / "keyword_bank.json"),
            },
            "video_center": {
                "path": video_center["path"],
                "keyword_count": len(video_center["video_keywords"]),
                "platform_search_count": len(video_center["platform_searches"]),
            },
            "team_execution": {
                "package_count": len(team_packages),
                "packages": team_packages,
            },
            "evidence_verification": {
                "dossier_count": len(list((ROOT / "memory" / "evidence").glob("*.json"))) if (ROOT / "memory" / "evidence").is_dir() else 0,
                "latest_path": str(ROOT / "memory" / "evidence" / "latest.json"),
            },
            "action_boards": {
                "board_count": len([item for item in (ROOT / "memory" / "action_boards").glob("*.json") if item.name != "latest.json"]) if (ROOT / "memory" / "action_boards").is_dir() else 0,
                "latest_path": str(ROOT / "memory" / "action_boards" / "latest.json"),
            },
            "team_response": {
                "latest_path": daily_team_response["json_path"],
                "report_path": daily_team_response["report_path"],
                "overall_score": daily_team_response["pack"]["quality_score"]["overall_score"],
                "human_approval_required": daily_team_response["pack"]["approval_boundary"]["human_approval_required"],
            },
            "war_room": {
                "latest_path": daily_war_room["json_path"],
                "report_path": daily_war_room["report_path"],
                "execution_queue_path": daily_war_room.get("execution_queue_path"),
                "execution_queue_report_path": daily_war_room.get("execution_queue_report_path"),
                "execution_queue_tasks": daily_war_room["war_room"].get("execution_queue", {}).get("summary", {}).get("task_count", 0),
                "execution_queue_blocked": daily_war_room["war_room"].get("execution_queue", {}).get("summary", {}).get("blocked_count", 0),
                "overall_score": daily_war_room["war_room"]["quality_score"]["overall_score"],
                "role_count": len(daily_war_room["war_room"]["team"]["roles"]),
                "search_gate": daily_war_room["war_room"]["search_confirmation"]["project_confirmation_gate"]["status"],
                "promotion_readiness": daily_war_room["war_room"]["project_execution"]["promotion_readiness"]["status"],
                "external_use_allowed": daily_war_room["war_room"]["approval_boundary"]["external_use_allowed"],
            },
        },
        "cases": cases,
    }
    write_json(ROOT / "memory" / "last_run.json", summary)
    report = build_headquarters_report(summary)
    write_text(ROOT / "reports" / "headquarters_status.md", report)
    owner_inbox = build_owner_inbox(summary)
    write_text(ROOT / "reports" / "owner_inbox.md", owner_inbox)
    mission_control = write_mission_control(ROOT)
    summary["v11_capabilities"]["mission_control"] = {
        "report_path": mission_control["report_path"],
        "json_path": mission_control["json_path"],
        "status": mission_control["snapshot"]["status"],
        "waiting_for_owner": mission_control["snapshot"]["command_center"]["waiting_for_owner"],
    }
    write_json(ROOT / "memory" / "last_run.json", summary)
    return summary


def main() -> None:
    summary = run_daily_cycle()
    print(
        "International Trade AI cycle complete: "
        f"{summary['case_count']} cases, "
        f"{summary['approval_count']} approvals, "
        f"{summary['major_matter_count']} major matters."
    )
    print(f"Last run: {ROOT / 'memory' / 'last_run.json'}")


if __name__ == "__main__":
    main()
