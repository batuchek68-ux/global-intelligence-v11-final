from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.comm.chat_gateway import build_chat_reply_draft, save_chat_reply_draft, send_approved_webhook_message
from backend.api.main import app
from backend.core.agents import AgentPool
from backend.core.orchestration import OrchestrationEngine
from backend.integrations.n8n_connector import N8NConnector
from backend.services.audit_service import append_audit, verify_append_only_marker
from backend.services.evidence_verification_service import build_evidence_dossier, verify_claim
from backend.services.intelligence_center_service import (
    build_intelligence_search_system,
    build_video_production_center,
    classify_intelligence_items,
    generate_intelligence_brief,
)
from backend.services.industry_war_room_service import build_industry_war_room
from backend.services.knowledge_benchmark_service import (
    build_industry_knowledge_base,
    build_v11_benchmark,
    compare_answers,
    score_answer,
)
from backend.services.mission_control_service import build_mission_control_snapshot, render_mission_control, write_mission_control
from backend.services.project_action_board_service import build_action_board, build_and_write_action_board
from backend.services.project_intelligence_service import (
    assess_promotion_readiness,
    build_feasibility_report,
    build_project_pipeline,
    build_project_record,
    build_project_search_plan,
    classify_project_stage,
    read_project_library,
)
from backend.services.self_improvement_service import build_self_improvement_plan, run_self_improvement_cycle
from backend.services.social_communication_service import assess_social_context, build_authorized_social_reply
from backend.services.team_execution_service import build_team_execution_package
from backend.services.team_response_service import build_team_response_pack
from backend.services.war_room_execution_queue_service import build_war_room_execution_queue
from backend.workflows.system_integrity import run_integrity_check


class V11OperationsTests(unittest.TestCase):
    def test_audit_service_only_appends(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "audit.log"
            append_audit("FIRST", "DONE", "one", path=path)
            append_audit("SECOND", "DONE", "two", path=path)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertIn("FIRST", lines[0])
            self.assertIn("SECOND", lines[1])
            self.assertTrue(verify_append_only_marker(path)["ok"])

    def test_chat_gateway_blocks_unapproved_send(self) -> None:
        draft = build_chat_reply_draft("wechat", "owner", "Draft reply")
        result = send_approved_webhook_message(draft)
        self.assertFalse(result["sent"])
        self.assertEqual(result["reason"], "human approval required")
        self.assertIn("draft_path", result)

    def test_chat_gateway_writes_draft_outbox(self) -> None:
        draft = build_chat_reply_draft("telegram", "owner", "Draft reply")
        path = save_chat_reply_draft(draft)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(data["approval_required"])
        self.assertEqual(data["status"], "draft_not_approved_for_sending")

    def test_n8n_connector_blocks_approval_gated_payload(self) -> None:
        result = N8NConnector(n8n_url="http://localhost:5678", api_key="token").trigger_workflow(
            "workflow",
            {"approval_required": True, "approved_by_human": False},
            "owner",
        )
        self.assertEqual(result["status"], "blocked_by_v11_risk_gate")

    def test_system_integrity_passes_core_checks(self) -> None:
        result = run_integrity_check(auto_fix=True)
        self.assertTrue(any(item["name"] == "audit:append_service_available" and item["ok"] for item in result["checks"]))
        self.assertTrue(any(item["name"] == "n8n:approval_gate_documented" and item["ok"] for item in result["checks"]))

    def test_desktop_prepare_resources_uses_v11_backend(self) -> None:
        script = Path("apps/desktop-cloud-os/scripts/prepare-resources.js").read_text(encoding="utf-8")
        self.assertIn('path.join(repoRoot, "backend")', script)
        self.assertNotIn("sourceRoot", script)

    def test_decision_hub_project_library_ui_is_readable_and_connected(self) -> None:
        html = Path("apps/decision-hub/public/index.html").read_text(encoding="utf-8")
        script = Path("apps/decision-hub/public/app.js").read_text(encoding="utf-8")

        self.assertIn("\u62db\u5546\u5f15\u8d44\u9879\u76ee\u5e93", html)
        self.assertIn("\u884c\u4e1a\u60c5\u62a5\u7b80\u62a5", html)
        self.assertIn("\u89c6\u9891\u5236\u4f5c\u4e2d\u5fc3", html)
        self.assertIn("\u56e2\u961f\u7b54\u590d\u5305", html)
        self.assertIn("\u884c\u4e1a\u4f5c\u6218\u5ba4", html)
        self.assertIn('data-view="briefing"', html)
        self.assertIn('data-view="project-library"', html)
        self.assertIn('data-view="war-room"', html)
        self.assertIn('data-view="team-response"', html)
        self.assertIn('data-view="video-center"', html)
        self.assertIn("\u5728\u5efa\u9879\u76ee", html)
        self.assertIn("\u8ba1\u5212\u5efa\u8bbe\u9879\u76ee", html)
        self.assertIn("\u5f85\u6838\u9a8c", html)
        self.assertIn("/api/projects/library", script)
        self.assertIn("/api/intelligence/brief", script)
        self.assertIn("/api/video/center", script)
        self.assertIn("/api/war-room/build", script)
        self.assertIn("/api/war-room/execution-queue", script)
        self.assertIn("/api/team/response", script)
        self.assertIn("renderProjectLibrary", script)
        self.assertIn("renderBriefing", script)
        self.assertIn("renderVideoCenter", script)
        self.assertIn("renderWarRoom", script)
        self.assertIn("renderWarRoomQueue", script)
        self.assertIn("renderTeamResponse", script)
        self.assertIn("loadWarRoomQueueBtn", html)
        self.assertIn("warRoomQueueResult", html)

        serialized = html + script
        for marker in ("\u935d", "\u6fe1\u5099\u7dbd", "\u7edb", "\u7487", "\ufffd"):
            self.assertNotIn(marker, serialized)

    def test_decision_hub_navigation_matches_views_and_core_apis(self) -> None:
        html = Path("apps/decision-hub/public/index.html").read_text(encoding="utf-8")
        script = Path("apps/decision-hub/public/app.js").read_text(encoding="utf-8")
        nav_views = re.findall(r'data-view="([^"]+)"', html)
        sections = re.findall(r'<section id="([^"]+)" class="view', html)

        self.assertEqual(set(nav_views), set(sections))
        for view in (
            "overview",
            "search",
            "briefing",
            "project-library",
            "evidence",
            "war-room",
            "team-response",
            "project",
            "video-center",
            "communication",
            "quality",
            "approval",
            "diagnostics",
        ):
            self.assertIn(view, nav_views)

        for endpoint in (
            "/api/search",
            "/api/intelligence/brief",
            "/api/projects/library",
            "/api/evidence/verify",
            "/api/war-room/build",
            "/api/war-room/execution-queue",
            "/api/team/response",
            "/api/team/execute",
            "/api/video/center",
            "/api/social/reply-draft",
            "/api/answers/score",
            "/api/benchmark/compare",
        ):
            self.assertIn(endpoint, script)

        for search_marker in (
            "search_expansion",
            "source_status",
            "result_categories",
            "candidate_projects",
            "project_brief_draft",
            "增强搜索词",
            "搜索源明细",
            "候选项目",
            "项目简报草稿",
        ):
            self.assertIn(search_marker, script)

    def test_api_strict_license_blocks_core_endpoints(self) -> None:
        env = {
            "CLOUD_OS_REQUIRE_LICENSE": "1",
            "CLOUD_OS_LICENSE_ENDPOINT": "",
            "CLOUD_OS_ENTERPRISE_ID": "",
            "CLOUD_OS_LICENSE_TOKEN": "",
        }
        with patch.dict(os.environ, env, clear=False):
            response = TestClient(app).post("/v1/search", json={"query": "哈萨克斯坦工程贸易"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["status"], "unconfigured")

    def test_api_chat_reply_is_draft_only(self) -> None:
        response = TestClient(app).post(
            "/v1/chat/reply-draft",
            json={"channel": "wechat", "recipient": "owner", "message": "Draft only"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["sent"])
        self.assertTrue(data["draft"]["approval_required"])
        self.assertEqual(data["reason"], "human approval required")

    def test_api_n8n_blocks_unapproved_payload(self) -> None:
        response = TestClient(app).post(
            "/v1/integrations/n8n/trigger/test-workflow",
            json={"approval_required": True, "approved_by_human": False},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ok"])
        self.assertEqual(response.json()["result"]["status"], "blocked_by_v11_risk_gate")

    def test_project_search_plan_prioritizes_government_confirmation(self) -> None:
        plan = build_project_search_plan("哈萨克斯坦工程贸易", "Kazakhstan")
        self.assertTrue(plan["queries"])
        self.assertEqual(plan["queries"][0]["intent"], "government_confirmation")
        self.assertIn("site:", plan["queries"][0]["query"])
        self.assertIn("gov.kz", plan["official_domains"])

    def test_project_stage_classification(self) -> None:
        planned = classify_project_stage("The government announced a planned feasibility study and EIA public hearing.")
        construction = classify_project_stage("The contract was awarded and construction started on site.")
        self.assertEqual(planned["category"], "planned")
        self.assertEqual(construction["category"], "under_construction")

    def test_project_record_extracts_government_evidence_and_stakeholders(self) -> None:
        record = build_project_record(
            "Kazakhstan logistics hub",
            "Kazakhstan",
            [
                {
                    "title": "Kazakhstan logistics hub investment project",
                    "url": "https://invest.gov.kz/projects/logistics-hub",
                    "source_type": "government",
                    "snippet": "The Ministry is the project owner. The planned feasibility study names an investor and developer.",
                }
            ],
        )
        self.assertEqual(record["confirmation_level"], "government_confirmed")
        self.assertEqual(record["category"], "planned")
        self.assertTrue(record["government_sources"])
        self.assertTrue(record["owner_candidates"])
        self.assertEqual(record["official_source_status"], "verified_project")
        self.assertEqual(record["project_record_status"], "verified_project")
        self.assertTrue(record["verified_project_allowed"])
        self.assertGreaterEqual(record["evidence_grade_summary"]["tier1_official_sources"], 1)
        self.assertEqual(record["promotion_readiness"]["status"], "draft_promotion_ready")
        self.assertTrue(record["promotion_readiness"]["can_generate_internal_promotion_draft"])
        self.assertFalse(record["promotion_readiness"]["approved_for_external_use"])

    def test_company_source_supports_candidate_but_cannot_verify_project_alone(self) -> None:
        record = build_project_record(
            "Kazakhstan logistics hub",
            "Kazakhstan",
            [
                {
                    "title": "Company announcement for Kazakhstan logistics hub",
                    "url": "https://example-logistics.com/news/hub",
                    "source_type": "official_company",
                    "snippet": "The developer announced a planned project with an investor and project owner.",
                }
            ],
        )
        self.assertEqual(record["official_source_status"], "official_company_supported")
        self.assertEqual(record["project_record_status"], "candidate_project")
        self.assertFalse(record["verified_project_allowed"])
        self.assertEqual(record["evidence_grade_summary"]["tier2_supporting_sources"], 1)
        self.assertIn("Missing Tier 1", " ".join(record["candidate_to_verified_gate"]["missing_requirements"]))

    def test_social_and_video_sources_remain_weak_signals_only(self) -> None:
        record = build_project_record(
            "Kazakhstan logistics hub",
            "Kazakhstan",
            [
                {
                    "title": "Forum rumor about Kazakhstan logistics hub",
                    "url": "https://t.me/example/123",
                    "source_type": "social",
                    "snippet": "A forum says the owner and developer are discussing a planned project.",
                }
            ],
        )
        self.assertEqual(record["official_source_status"], "weak_signal_only")
        self.assertEqual(record["project_record_status"], "candidate_project")
        self.assertFalse(record["verified_project_allowed"])
        self.assertEqual(record["evidence_grade_summary"]["weak_signal_sources"], 1)
        self.assertEqual(record["promotion_readiness"]["status"], "lead_only")

    def test_promotion_readiness_blocks_weak_project_leads(self) -> None:
        readiness = assess_promotion_readiness(
            {
                "confirmation_level": "unverified_or_secondary",
                "confidence": 55,
                "category": "unknown",
                "government_sources": [],
                "owner_candidates": [],
                "developer_candidates": [],
            }
        )
        self.assertEqual(readiness["status"], "lead_only")
        self.assertFalse(readiness["can_generate_internal_promotion_draft"])
        self.assertIn("Do not use as an investment-promotion project", " ".join(readiness["allowed_internal_actions"]))
        self.assertIn("formal investment-promotion publication", readiness["blocked_actions"])

    def test_evidence_dossier_grades_sources_and_blocks_weak_high_risk_claims(self) -> None:
        dossier = build_evidence_dossier(
            "Kazakhstan EPC customs tariff and delivery commitment",
            [
                {
                    "title": "Telegram rumor about project delivery",
                    "url": "https://t.me/example/1",
                    "snippet": "customs tariff and delivery date are confirmed by a group member",
                    "source_type": "social",
                }
            ],
            project="Kazakhstan EPC",
            country="Kazakhstan",
        )
        self.assertEqual(dossier["verification_status"], "weak_signal_only")
        self.assertTrue(dossier["requires_human_review"])
        self.assertIn("formal outreach", dossier["blocked_actions"])

    def test_evidence_dossier_recognizes_official_customs_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_EVIDENCE_MEMORY_DIR": str(Path(temp) / "memory"),
                "V11_EVIDENCE_REPORT_DIR": str(Path(temp) / "reports"),
            }
            with patch.dict(os.environ, env, clear=False):
                result = verify_claim(
                    "Kazakhstan mining equipment customs documents",
                    [
                        {
                            "title": "Customs documents for import",
                            "url": "https://customs.gov.kz/import-documents",
                            "snippet": "official customs authority explains HS code, tariff and documents",
                            "source_type": "customs",
                        }
                    ],
                    project="Mining equipment",
                    country="Kazakhstan",
                )
        self.assertTrue(result["ok"])
        dossier = result["dossier"]
        self.assertEqual(dossier["verification_status"], "officially_supported")
        self.assertGreaterEqual(dossier["confidence"], 90)
        self.assertTrue(Path(result["json_path"]).name.endswith(".json"))

    def test_api_project_discover_and_feasibility_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_PROJECT_LIBRARY_PATH": str(Path(temp) / "projects.json"),
                "V11_FEASIBILITY_DIR": str(Path(temp) / "feasibility"),
            }
            with patch.dict(os.environ, env, clear=False):
                client = TestClient(app)
                response = client.post(
                    "/v1/projects/discover",
                    json={
                        "topic": "Kazakhstan industrial park",
                        "country": "Kazakhstan",
                        "evidence": [
                            {
                                "title": "Industrial park investment project",
                                "url": "https://gov.kz/memleket/entities/example/projects/industrial-park",
                                "source_type": "government",
                                "snippet": "Akimat is the government authority. The project is planned with feasibility study and investor selection.",
                            }
                        ],
                    },
                )
                self.assertEqual(response.status_code, 200)
                project = response.json()["projects"][0]
                self.assertEqual(project["confirmation_level"], "government_confirmed")

                report = client.post("/v1/reports/feasibility", json={"project": project})
                self.assertEqual(report.status_code, 200)
                self.assertFalse(report.json()["approved_for_sending"])
                self.assertIn("DRAFT - Not approved for sending", report.json()["content"])

    def test_project_pipeline_turns_search_evidence_into_execution_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_PROJECT_LIBRARY_PATH": str(Path(temp) / "projects.json"),
                "V11_FEASIBILITY_DIR": str(Path(temp) / "feasibility"),
                "V11_ACTION_BOARD_MEMORY_DIR": str(Path(temp) / "boards_memory"),
                "V11_ACTION_BOARD_REPORT_DIR": str(Path(temp) / "boards_reports"),
            }
            with patch.dict(os.environ, env, clear=False):
                result = build_project_pipeline(
                    "Kazakhstan logistics hub investment project",
                    "Kazakhstan",
                    [
                        {
                            "title": "Kazakhstan logistics hub official investment project",
                            "url": "https://invest.gov.kz/projects/logistics-hub",
                            "source_type": "government",
                            "snippet": "Akimat is the government authority. Ministry project owner. Planned feasibility study names investor and developer.",
                        }
                    ],
                )
        self.assertTrue(result["ok"])
        self.assertEqual(result["mode"], "project_intelligence_pipeline")
        self.assertEqual(result["project"]["confirmation_level"], "government_confirmed")
        self.assertEqual(result["promotion_readiness"]["status"], "draft_promotion_ready")
        self.assertTrue(result["promotion_readiness"]["human_approval_required_for_external_use"])
        self.assertTrue(result["project"]["owner_candidates"])
        self.assertTrue(result["project"]["developer_candidates"])
        self.assertTrue(result["action_board"])
        self.assertFalse(result["feasibility_report"]["approved_for_sending"])
        self.assertIn("external outreach", result["blocked_actions"])

    def test_project_library_summary_groups_construction_planned_and_unconfirmed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            library_path = Path(temp) / "projects.json"
            library_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "p1",
                            "title": "Mine logistics terminal",
                            "category": "under_construction",
                            "confirmation_level": "government_confirmed",
                            "confidence": 94,
                            "owner_candidates": ["Ministry owner"],
                            "developer_candidates": ["Developer"],
                        },
                        {
                            "id": "p2",
                            "title": "Industrial park",
                            "category": "planned",
                            "confirmation_level": "government_confirmed",
                            "confidence": 91,
                        },
                        {
                            "id": "p3",
                            "title": "Weak social signal",
                            "category": "unknown",
                            "confirmation_level": "unverified_or_secondary",
                            "confidence": 55,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"V11_PROJECT_LIBRARY_PATH": str(library_path)}, clear=False):
                library = read_project_library()

        self.assertEqual(library["summary"]["total"], 3)
        self.assertEqual(library["summary"]["under_construction"], 1)
        self.assertEqual(library["summary"]["planned"], 1)
        self.assertEqual(library["summary"]["unconfirmed"], 1)
        self.assertEqual(library["summary"]["official_ready"], 2)
        self.assertEqual(library["summary"]["needs_evidence"], 1)
        self.assertEqual(library["summary"]["promotion_draft_ready"], 1)
        self.assertEqual(library["high_value_watchlist"][0]["id"], "p1")

    def test_api_project_pipeline_returns_library_action_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_PROJECT_LIBRARY_PATH": str(Path(temp) / "projects.json"),
                "V11_FEASIBILITY_DIR": str(Path(temp) / "feasibility"),
                "V11_ACTION_BOARD_MEMORY_DIR": str(Path(temp) / "boards_memory"),
                "V11_ACTION_BOARD_REPORT_DIR": str(Path(temp) / "boards_reports"),
            }
            with patch.dict(os.environ, env, clear=False):
                response = TestClient(app).post(
                    "/v1/projects/pipeline",
                    json={
                        "topic": "Kazakhstan industrial park project",
                        "country": "Kazakhstan",
                        "evidence": [
                            {
                                "title": "Industrial park official project",
                                "url": "https://gov.kz/memleket/entities/example/projects/industrial-park",
                                "source_type": "government",
                                "snippet": "The akimat is the authority. The project is planned with investor selection and developer participation.",
                            }
                        ],
                    },
                )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["mode"], "project_intelligence_pipeline")
        self.assertTrue(data["project_library"]["updated"])
        self.assertTrue(data["action_board"])
        self.assertFalse(data["feasibility_report"]["approved_for_sending"])
        self.assertIn("Request human approval", " ".join(data["next_actions"]))

    def test_api_evidence_verify_returns_dossier(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_EVIDENCE_MEMORY_DIR": str(Path(temp) / "memory"),
                "V11_EVIDENCE_REPORT_DIR": str(Path(temp) / "reports"),
            }
            with patch.dict(os.environ, env, clear=False):
                response = TestClient(app).post(
                    "/v1/evidence/verify",
                    json={
                        "claim": "Kazakhstan project owner is confirmed by government procurement",
                        "project": "Kazakhstan logistics hub",
                        "country": "Kazakhstan",
                        "evidence": [
                            {
                                "title": "Government procurement project",
                                "url": "https://goszakup.gov.kz/project",
                                "snippet": "official procurement page names project owner",
                                "source_type": "procurement",
                            }
                        ],
                    },
                )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["dossier"]["verification_status"], "officially_supported")

    def test_project_action_board_turns_case_and_evidence_into_role_tasks(self) -> None:
        case = {
            "created_at": "2026-06-23T00:00:00+00:00",
            "project": {
                "title": "Kazakhstan Logistics Hub",
                "country": "Kazakhstan",
                "stage": "proposal",
                "next_decision": "Approve outreach?",
            },
            "classification": {"is_major_matter": True},
            "judgment": {"level": "high", "score": 91},
        }
        dossier = {"id": "ev1", "verification_status": "weak_signal_only", "confidence": 45, "requires_human_review": True}
        board = build_action_board(case, dossier)
        self.assertTrue(board["risk_gate"]["blocked"])
        self.assertEqual(board["risk_gate"]["status"], "pending_owner")
        self.assertEqual(board["summary"]["task_count"], 6)
        roles = {task["role"] for task in board["tasks"]}
        self.assertIn("trade_lead", roles)
        self.assertIn("risk_approval_officer", roles)

    def test_project_action_board_writes_latest_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_ACTION_BOARD_MEMORY_DIR": str(Path(temp) / "memory"),
                "V11_ACTION_BOARD_REPORT_DIR": str(Path(temp) / "reports"),
            }
            case = {
                "created_at": "2026-06-23T00:00:00+00:00",
                "project": {"title": "Internal cleanup", "country": "Internal", "stage": "internal"},
                "classification": {"is_major_matter": False},
                "judgment": {"level": "low", "score": 20},
            }
            with patch.dict(os.environ, env, clear=False):
                result = build_and_write_action_board(case, {"verification_status": "officially_supported", "confidence": 95, "requires_human_review": False})
                self.assertTrue(result["ok"])
                self.assertTrue(Path(result["json_path"]).is_file())
                self.assertTrue(Path(result["report_path"]).is_file())

    def test_api_project_action_board_returns_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_ACTION_BOARD_MEMORY_DIR": str(Path(temp) / "memory"),
                "V11_ACTION_BOARD_REPORT_DIR": str(Path(temp) / "reports"),
            }
            with patch.dict(os.environ, env, clear=False):
                response = TestClient(app).post(
                    "/v1/projects/action-board",
                    json={
                        "case": {
                            "created_at": "2026-06-23T00:00:00+00:00",
                            "project": {"title": "Kazakhstan Logistics", "country": "Kazakhstan", "stage": "planned"},
                            "classification": {"is_major_matter": False},
                            "judgment": {"level": "medium", "score": 60},
                        },
                        "evidence_dossier": {
                            "id": "ev2",
                            "verification_status": "officially_supported",
                            "confidence": 95,
                            "requires_human_review": False,
                        },
                    },
                )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["board"]["summary"]["task_count"], 6)

    def test_feasibility_report_blocks_external_use_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"V11_FEASIBILITY_DIR": temp}, clear=False):
                result = build_feasibility_report({"title": "Test Project", "confidence": 60})
                self.assertTrue(result["ok"])
                self.assertFalse(result["approved_for_sending"])
                self.assertIn("No government source confirmed yet", result["content"])

    def test_intelligence_search_system_covers_all_domains(self) -> None:
        system = build_intelligence_search_system(
            ["Kazakhstan engineering trade"],
            ["Kazakhstan"],
            ["logistics", "mining"],
        )
        category_ids = {item["id"] for item in system["categories"]}
        self.assertIn("political_impact", category_ids)
        self.assertIn("forums_social", category_ids)
        self.assertIn("video_intelligence", category_ids)
        self.assertTrue(any("site:gov" in query["query"] or "site:gov.kz" in query["query"] for item in system["categories"] for query in item["queries"]))

    def test_intelligence_items_are_scored_and_classified(self) -> None:
        classified = classify_intelligence_items(
            [
                {
                    "title": "Government announces billion dollar logistics tender with high public attention",
                    "summary": "Minister policy update, tender, EPC contractor, YouTube trending analysis",
                    "source_type": "government",
                }
            ]
        )
        self.assertTrue(classified["buckets"]["high_value"])
        self.assertTrue(classified["buckets"]["political_impact"])
        self.assertTrue(classified["buckets"]["high_attention"])
        self.assertTrue(classified["buckets"]["project_critical"])

    def test_intelligence_brief_and_video_center_are_draft_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_KEYWORD_BANK_PATH": str(Path(temp) / "keyword_bank.json"),
                "V11_INTELLIGENCE_BRIEF_DIR": str(Path(temp) / "briefs"),
                "V11_VIDEO_CENTER_DIR": str(Path(temp) / "video"),
            }
            with patch.dict(os.environ, env, clear=False):
                brief = generate_intelligence_brief(
                    ["Kazakhstan engineering trade"],
                    ["Kazakhstan"],
                    ["logistics"],
                    [{"title": "Government logistics tender", "summary": "policy tender investment", "source_type": "government"}],
                )
                video = build_video_production_center(["engineering trade"], ["Kazakhstan"], ["logistics"])
        self.assertTrue(brief["ok"])
        self.assertIn("DRAFT - internal intelligence", brief["content"])
        self.assertTrue(video["video_keywords"])
        self.assertTrue(video["platform_searches"])
        self.assertIn("Video drafts are internal", video["rules"][0])

    def test_industry_war_room_combines_search_project_team_video_and_risk(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_WAR_ROOM_MEMORY_DIR": str(Path(temp) / "war_room_memory"),
                "V11_WAR_ROOM_REPORT_DIR": str(Path(temp) / "war_room_reports"),
                "V11_WAR_ROOM_EXECUTION_MEMORY_DIR": str(Path(temp) / "war_room_queue_memory"),
                "V11_WAR_ROOM_EXECUTION_REPORT_DIR": str(Path(temp) / "war_room_queue_reports"),
                "V11_TEAM_RESPONSE_MEMORY_DIR": str(Path(temp) / "team_memory"),
                "V11_TEAM_RESPONSE_REPORT_DIR": str(Path(temp) / "team_reports"),
                "V11_VIDEO_CENTER_DIR": str(Path(temp) / "video"),
            }
            with patch.dict(os.environ, env, clear=False):
                result = build_industry_war_room(
                    "Kazakhstan engineering trade project customs investment promotion video",
                    country="Kazakhstan",
                    industries=["infrastructure", "logistics"],
                    evidence=[],
                )
                self.assertTrue(result["ok"])
                room = result["war_room"]
                self.assertEqual(room["mode"], "industry_war_room")
                self.assertEqual(room["search_confirmation"]["project_confirmation_gate"]["status"], "lead_only")
                self.assertEqual(room["project_execution"]["promotion_readiness"]["status"], "lead_only")
                self.assertGreaterEqual(len(room["team"]["roles"]), 6)
                self.assertTrue(room["video_center"]["platform_searches"])
                self.assertFalse(room["approval_boundary"]["external_use_allowed"])
                self.assertGreaterEqual(room["quality_score"]["overall_score"], 70)
                self.assertGreaterEqual(room["execution_queue"]["summary"]["task_count"], 12)
                self.assertGreater(room["execution_queue"]["summary"]["blocked_count"], 0)
                self.assertTrue(Path(result["report_path"]).is_file())
                self.assertTrue(Path(result["execution_queue_path"]).is_file())
                self.assertTrue(Path(result["execution_queue_report_path"]).is_file())

    def test_war_room_execution_queue_tracks_evidence_video_and_approval_work(self) -> None:
        room = build_industry_war_room(
            "Kazakhstan engineering trade project customs investment promotion video",
            country="Kazakhstan",
            industries=["infrastructure", "logistics"],
            evidence=[],
            persist=False,
        )["war_room"]
        queue = build_war_room_execution_queue(room)

        self.assertEqual(queue["mode"], "war_room_execution_queue")
        self.assertGreaterEqual(queue["summary"]["task_count"], 12)
        self.assertGreater(queue["summary"]["blocked_count"], 0)
        self.assertGreater(queue["summary"]["approval_required_count"], 0)
        self.assertTrue(any(task["source"].startswith("search_confirmation") for task in queue["tasks"]))
        self.assertTrue(any(task["role"] == "video_media_producer" for task in queue["tasks"]))
        self.assertTrue(any("public publishing" in task["blocked_actions"] for task in queue["tasks"]))

    def test_api_war_room_execution_queue_returns_latest_queue(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_WAR_ROOM_MEMORY_DIR": str(Path(temp) / "war_room_memory"),
                "V11_WAR_ROOM_REPORT_DIR": str(Path(temp) / "war_room_reports"),
                "V11_WAR_ROOM_EXECUTION_MEMORY_DIR": str(Path(temp) / "war_room_queue_memory"),
                "V11_WAR_ROOM_EXECUTION_REPORT_DIR": str(Path(temp) / "war_room_queue_reports"),
                "V11_TEAM_RESPONSE_MEMORY_DIR": str(Path(temp) / "team_memory"),
                "V11_TEAM_RESPONSE_REPORT_DIR": str(Path(temp) / "team_reports"),
                "V11_VIDEO_CENTER_DIR": str(Path(temp) / "video"),
            }
            with patch.dict(os.environ, env, clear=False):
                build = TestClient(app).post(
                    "/v1/war-room/build",
                    json={
                        "objective": "Kazakhstan engineering trade project customs investment promotion video",
                        "country": "Kazakhstan",
                        "industries": ["infrastructure", "logistics"],
                    },
                )
                self.assertEqual(build.status_code, 200)
                response = TestClient(app).get("/v1/war-room/execution-queue")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["queue"]["mode"], "war_room_execution_queue")
        self.assertGreaterEqual(data["queue"]["summary"]["task_count"], 12)
        self.assertIn("Read-only queue view", data["note"])

    def test_api_war_room_build_returns_vertical_operating_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_WAR_ROOM_MEMORY_DIR": str(Path(temp) / "war_room_memory"),
                "V11_WAR_ROOM_REPORT_DIR": str(Path(temp) / "war_room_reports"),
                "V11_TEAM_RESPONSE_MEMORY_DIR": str(Path(temp) / "team_memory"),
                "V11_TEAM_RESPONSE_REPORT_DIR": str(Path(temp) / "team_reports"),
                "V11_VIDEO_CENTER_DIR": str(Path(temp) / "video"),
            }
            with patch.dict(os.environ, env, clear=False):
                response = TestClient(app).post(
                    "/v1/war-room/build",
                    json={
                        "objective": "Kazakhstan engineering trade project customs investment promotion video",
                        "country": "Kazakhstan",
                        "industries": ["infrastructure", "logistics"],
                    },
                )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["war_room"]["mode"], "industry_war_room")
        self.assertEqual(data["war_room"]["operating_rule"].split(":")[0], "v11 works as a vertical industry project team")

    def test_api_intelligence_and_video_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_KEYWORD_BANK_PATH": str(Path(temp) / "keyword_bank.json"),
                "V11_INTELLIGENCE_BRIEF_DIR": str(Path(temp) / "briefs"),
                "V11_VIDEO_CENTER_DIR": str(Path(temp) / "video"),
            }
            with patch.dict(os.environ, env, clear=False):
                client = TestClient(app)
                system = client.post("/v1/intelligence/search-system", json={"topic": "Kazakhstan engineering trade"})
                self.assertEqual(system.status_code, 200)
                self.assertTrue(system.json()["categories"])

                brief = client.post(
                    "/v1/intelligence/brief",
                    json={
                        "topic": "Kazakhstan engineering trade",
                        "items": [{"title": "Tender policy", "summary": "government tender project", "source_type": "government"}],
                    },
                )
                self.assertEqual(brief.status_code, 200)
                self.assertIn("DRAFT - internal intelligence", brief.json()["content"])

                video = client.post("/v1/video/center", json={"topic": "engineering trade", "country": "Kazakhstan"})
                self.assertEqual(video.status_code, 200)
                self.assertTrue(video.json()["platform_searches"])

    def test_self_improvement_plan_tracks_domain_scores_and_boundaries(self) -> None:
        plan = build_self_improvement_plan(
            {
                "tests_passed": 71,
                "tests_total": 71,
                "cloud_acceptance_ok": True,
                "system_integrity_ok": True,
                "search_system_ok": True,
                "social_gate_ok": True,
            }
        )
        self.assertTrue(plan["ok"])
        self.assertIn("international_trade", plan["assessment"]["domain_scores"])
        self.assertIn("social_communication", plan["assessment"]["domain_scores"])
        self.assertIn("external social posting", plan["repair_policy"]["blocked_without_human"])

    def test_self_improvement_cycle_uses_temp_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_SELF_IMPROVEMENT_STATE": str(Path(temp) / "state.json"),
                "V11_SELF_IMPROVEMENT_REPORT_DIR": str(Path(temp) / "reports"),
            }
            with patch.dict(os.environ, env, clear=False):
                result = run_self_improvement_cycle({"tests_passed": 71, "tests_total": 71, "cloud_acceptance_ok": True})
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["cycle"]["overall_score"], 80)

    def test_social_communication_blocks_unapproved_high_risk_external_reply(self) -> None:
        assessment = assess_social_context(
            "wechat",
            "Can you confirm price, contract, payment and delivery date for the government project?",
            authorization={"scope": "draft_only"},
            evidence=[],
            audience="external",
        )
        self.assertEqual(assessment["action"], "draft_only")
        self.assertTrue(assessment["needs_human_approval"])
        self.assertEqual(assessment["risk_level"], "high")

    def test_social_reply_draft_keeps_message_unsent(self) -> None:
        result = build_authorized_social_reply(
            "telegram",
            "partner",
            "Who is the developer and can we promise participation?",
            authorization={"scope": "draft_only"},
            evidence=[{"source_type": "government", "url": "https://gov.kz/project"}],
        )
        self.assertTrue(result["ok"])
        self.assertFalse(result["sent"])
        self.assertIn("DRAFT - Not approved for sending", result["draft"]["message"])
        self.assertIn("internal_review", result["draft"]["context"])
        self.assertIn("approval_checklist", result["draft"]["context"])
        self.assertIn("风控负责人", " ".join(result["internal_review"]["team_judgment"]))
        self.assertTrue(any("人工审批" in item for item in result["approval_checklist"]))
        self.assertIn("不能正式承诺报价", result["draft"]["message"])

    def test_api_self_improvement_and_social_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_SELF_IMPROVEMENT_STATE": str(Path(temp) / "state.json"),
                "V11_SELF_IMPROVEMENT_REPORT_DIR": str(Path(temp) / "reports"),
            }
            with patch.dict(os.environ, env, clear=False):
                client = TestClient(app)
                plan = client.post("/v1/system/self-improvement/plan", json={"tests_passed": 71, "tests_total": 71})
                self.assertEqual(plan.status_code, 200)
                self.assertIn("software_operations", plan.json()["assessment"]["domain_scores"])

                run = client.post("/v1/system/self-improvement/run", json={"tests_passed": 71, "tests_total": 71})
                self.assertEqual(run.status_code, 200)
                self.assertTrue(run.json()["ok"])

                social = client.post(
                    "/v1/social/analyze",
                    json={"channel": "wechat", "message": "Please quote price and delivery date", "authorization": {"scope": "draft_only"}},
                )
                self.assertEqual(social.status_code, 200)
                self.assertEqual(social.json()["action"], "draft_only")

    def test_industry_knowledge_base_includes_customs_information(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"V11_KNOWLEDGE_BASE_PATH": str(Path(temp) / "knowledge.json")}, clear=False):
                result = build_industry_knowledge_base()
        self.assertTrue(result["ok"])
        domains = result["data"]["domains"]
        self.assertIn("customs_information", domains)
        self.assertIn("HS code classification", domains["customs_information"]["topics"])
        self.assertTrue(domains["customs_information"]["risk_rules"])

    def test_v11_benchmark_has_50_questions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"V11_BENCHMARK_PATH": str(Path(temp) / "benchmark.json")}, clear=False):
                result = build_v11_benchmark()
        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["question_count"], 50)
        self.assertTrue(any(item["domain"] == "customs_information" for item in result["data"]["questions"]))

    def test_answer_scorer_rewards_evidence_action_and_risk(self) -> None:
        result = score_answer(
            "如何确认哈萨克斯坦进口矿山设备的 HS 编码、关税和清关文件？",
            "Use official customs source URL and date, verify HS code, tariff, customs valuation, certificate of origin, export control risk, and build a checklist with next steps.",
            evidence=[{"url": "https://customs.gov.example", "source_type": "official"}],
        )
        self.assertGreaterEqual(result["overall_score"], 70)
        self.assertIn("risk_judgment", result["dimensions"])
        self.assertIn("professional_depth", result["dimensions"])

    def test_compare_answers_ranks_v11_style_answer(self) -> None:
        result = compare_answers(
            "如何确认进口设备海关信息？",
            {
                "v11": "Check official customs URL and date, verify HS code, tariff, customs valuation, documents, risk, approval boundary, and next step checklist.",
                "generic": "You can search online and ask an expert.",
            },
        )
        self.assertEqual(result["ranked"][0]["name"], "v11")

    def test_api_knowledge_benchmark_and_answer_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_KNOWLEDGE_BASE_PATH": str(Path(temp) / "knowledge.json"),
                "V11_BENCHMARK_PATH": str(Path(temp) / "benchmark.json"),
            }
            with patch.dict(os.environ, env, clear=False):
                client = TestClient(app)
                knowledge = client.post("/v1/knowledge/build")
                self.assertEqual(knowledge.status_code, 200)
                self.assertIn("customs_information", knowledge.json()["data"]["domains"])

                benchmark = client.post("/v1/benchmark/build")
                self.assertEqual(benchmark.status_code, 200)
                self.assertEqual(benchmark.json()["data"]["question_count"], 50)

                score = client.post(
                    "/v1/answers/score",
                    json={
                        "question": "如何确认海关信息？",
                        "answer": "Use official customs source URL, HS code, tariff, risk, approval, and checklist.",
                    },
                )
                self.assertEqual(score.status_code, 200)
                self.assertIn("overall_score", score.json())

    def test_team_execution_package_behaves_like_project_team(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_TEAM_EXECUTION_MEMORY_DIR": str(Path(temp) / "memory"),
                "V11_TEAM_EXECUTION_REPORT_DIR": str(Path(temp) / "reports"),
            }
            with patch.dict(os.environ, env, clear=False):
                package = build_team_execution_package(
                    "Kazakhstan mining logistics EPC招商引资 and customs risk",
                    country="Kazakhstan",
                    industries=["mining", "logistics"],
                    evidence=[{"source_type": "government", "url": "https://gov.kz/project", "snippet": "planned feasibility study"}],
                )
        self.assertTrue(package["ok"])
        roles = {item["role"] for item in package["team_roles"]}
        self.assertIn("trade_lead", roles)
        self.assertIn("research_analyst", roles)
        self.assertIn("investment_promotion_lead", roles)
        self.assertIn("video_media_producer", roles)
        self.assertIn("project_manager", roles)
        self.assertIn("risk_approval_officer", roles)
        self.assertTrue(package["deliverables"])
        self.assertTrue(package["search_plan"]["video_platform_searches"])
        self.assertTrue(package["risk"]["needs_human_approval"])

    def test_api_team_execute_returns_execution_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_TEAM_EXECUTION_MEMORY_DIR": str(Path(temp) / "memory"),
                "V11_TEAM_EXECUTION_REPORT_DIR": str(Path(temp) / "reports"),
            }
            with patch.dict(os.environ, env, clear=False):
                response = TestClient(app).post(
                    "/v1/team/execute",
                    json={
                        "objective": "Build an investment promotion and project execution plan for Kazakhstan logistics hub",
                        "country": "Kazakhstan",
                        "industries": ["logistics", "infrastructure"],
                    },
                )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["operating_rule"].split(":")[0], "v11 acts as a project team")

    def test_team_response_pack_answers_like_project_team(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_TEAM_RESPONSE_MEMORY_DIR": str(Path(temp) / "memory"),
                "V11_TEAM_RESPONSE_REPORT_DIR": str(Path(temp) / "reports"),
            }
            with patch.dict(os.environ, env, clear=False):
                result = build_team_response_pack(
                    "哈萨克斯坦工程贸易项目如何推进？",
                    metadata={"country": "Kazakhstan", "industries": ["logistics", "mining"]},
                    evidence=[{"title": "official project page", "url": "https://gov.kz/project", "source_type": "government", "snippet": "official evidence"}],
                )
                self.assertTrue(Path(result["json_path"]).is_file())
                self.assertTrue(Path(result["report_path"]).is_file())
        pack = result["pack"]
        self.assertTrue(pack["ok"])
        self.assertEqual(pack["mode"], "team_response_pack")
        self.assertGreaterEqual(len(pack["team_roles"]), 6)
        self.assertGreaterEqual(pack["quality_score"]["overall_score"], 70)
        self.assertIn("结论", pack["executive_answer"])
        self.assertIn("执行清单", pack["executive_answer"])
        self.assertIn("风险边界", pack["executive_answer"])
        self.assertIn("国际贸易负责人", {item["label"] for item in pack["team_roles"]})
        self.assertIn("风控审批负责人", {item["label"] for item in pack["team_roles"]})
        self.assertTrue(pack["approval_boundary"]["draft_only"])
        serialized = json.dumps(pack, ensure_ascii=False)
        for marker in ("鍝", "濡備綍", "绛", "璇", "�"):
            self.assertNotIn(marker, serialized)

    def test_api_team_response_and_query_return_team_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_TEAM_RESPONSE_MEMORY_DIR": str(Path(temp) / "memory"),
                "V11_TEAM_RESPONSE_REPORT_DIR": str(Path(temp) / "reports"),
            }
            with patch.dict(os.environ, env, clear=False):
                client = TestClient(app)
                response = client.post(
                    "/v1/team/response",
                    json={"question": "Kazakhstan EPC trade opportunity", "country": "Kazakhstan"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["pack"]["mode"], "team_response_pack")

                query = client.post(
                    "/v1/query",
                    json={"query": "Kazakhstan EPC trade opportunity", "metadata": {"country": "Kazakhstan"}},
                )
                self.assertEqual(query.status_code, 200)
                self.assertEqual(query.json()["mode"], "team_response_pack")
                self.assertIn("team_response", query.json())
                self.assertEqual(query.json()["orchestration"]["status"], "success")
                result = query.json()["orchestration"]["result"]
                self.assertEqual(result["status"], "team_orchestration_ready")
                self.assertTrue(result["evidence_plan"])
                self.assertIn("risk_gate", result)

    def test_agent_pool_and_orchestration_use_v11_industry_team(self) -> None:
        pool = AgentPool()
        self.assertEqual(pool.health_check()["mode"], "v11_vertical_industry_team")
        self.assertIn("evidence_planner", pool.health_check()["agents"])

    def test_orchestration_returns_evidence_risk_and_team_steps(self) -> None:
        async def run_case() -> dict:
            pool = AgentPool()
            engine = OrchestrationEngine({})
            for agent_type, agent in pool.get_all_agents().items():
                engine.register_agent(agent_type, agent)
            return await engine.execute_query(
                "哈萨克斯坦工程贸易 海关 关税 项目负责人 招商",
                org_id="owner",
                user_id="tester",
                metadata={"country": "Kazakhstan"},
            )

        result = __import__("asyncio").run(run_case())
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["result"]["status"], "team_orchestration_ready")
        self.assertEqual(result["result"]["intent"], "customs_trade_risk")
        self.assertTrue(result["result"]["evidence_plan"])
        self.assertTrue(result["result"]["risk_gate"]["needs_human_approval"])
        self.assertTrue(result["result"]["team_next_steps"])

    def test_mission_control_snapshot_unifies_execution_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "memory" / "knowledge_base").mkdir(parents=True)
            (root / "memory" / "benchmark").mkdir(parents=True)
            (root / "memory" / "intelligence").mkdir(parents=True)
            (root / "memory" / "action_boards").mkdir(parents=True)
            (root / "memory" / "team_responses").mkdir(parents=True)
            (root / "memory" / "war_room").mkdir(parents=True)
            (root / "memory" / "war_room_execution").mkdir(parents=True)
            (root / "reports" / "benchmark").mkdir(parents=True)
            (root / "reports" / "intelligence_briefs").mkdir(parents=True)
            (root / "reports" / "video_center").mkdir(parents=True)
            (root / "reports" / "team_execution").mkdir(parents=True)
            (root / "reports" / "action_boards").mkdir(parents=True)
            (root / "reports" / "team_responses").mkdir(parents=True)
            (root / "reports" / "war_room").mkdir(parents=True)
            (root / "reports" / "war_room_execution").mkdir(parents=True)
            (root / "reports").mkdir(exist_ok=True)
            (root / "memory" / "last_run.json").write_text(
                json.dumps(
                    {
                        "project_count": 1,
                        "case_count": 1,
                        "major_matter_count": 1,
                        "cases": [
                            {
                                "project": {"title": "Kazakhstan Logistics", "country": "Kazakhstan", "next_decision": "approve outreach?"},
                                "classification": {"is_major_matter": True},
                                "judgment": {"level": "high", "triggers": ["customs"]},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (root / "memory" / "knowledge_base" / "industry_knowledge.json").write_text(
                json.dumps({"domains": {"customs_information": {}, "epc_projects": {}}}),
                encoding="utf-8",
            )
            (root / "memory" / "benchmark" / "v11_benchmark_50.json").write_text(
                json.dumps({"question_count": 50}),
                encoding="utf-8",
            )
            (root / "reports" / "benchmark" / "daily_answer_score.json").write_text(
                json.dumps({"overall_score": 86, "verdict": "excellent"}),
                encoding="utf-8",
            )
            (root / "memory" / "intelligence" / "keyword_bank.json").write_text(
                json.dumps({"keywords": [{"keyword": "Kazakhstan customs HS code EPC"}]}),
                encoding="utf-8",
            )
            (root / "reports" / "owner_inbox.md").write_text("# Owner Inbox\n", encoding="utf-8")
            (root / "reports" / "intelligence_briefs" / "today.md").write_text("# Brief\n", encoding="utf-8")
            (root / "reports" / "video_center" / "today.json").write_text("{}", encoding="utf-8")
            (root / "reports" / "team_execution" / "pkg.md").write_text("# Team\n", encoding="utf-8")
            (root / "memory" / "action_boards" / "latest.json").write_text(
                json.dumps({"risk_gate": {"status": "open"}, "summary": {"task_count": 6}}),
                encoding="utf-8",
            )
            (root / "memory" / "action_boards" / "board.json").write_text("{}", encoding="utf-8")
            (root / "reports" / "action_boards" / "board.md").write_text("# Board\n", encoding="utf-8")
            (root / "memory" / "team_responses" / "latest.json").write_text(
                json.dumps({"mode": "team_response_pack", "quality_score": {"overall_score": 88}, "team_roles": [1, 2, 3, 4, 5, 6]}),
                encoding="utf-8",
            )
            (root / "memory" / "team_responses" / "response.json").write_text("{}", encoding="utf-8")
            (root / "reports" / "team_responses" / "response.md").write_text("# Response\n", encoding="utf-8")
            (root / "memory" / "war_room" / "latest.json").write_text(
                json.dumps(
                    {
                        "mode": "industry_war_room",
                        "quality_score": {"overall_score": 91},
                        "team": {"roles": [1, 2, 3, 4, 5, 6]},
                        "search_confirmation": {"project_confirmation_gate": {"status": "lead_only"}},
                        "project_execution": {"promotion_readiness": {"status": "lead_only"}},
                        "approval_boundary": {"external_use_allowed": False},
                    }
                ),
                encoding="utf-8",
            )
            (root / "memory" / "war_room" / "room.json").write_text("{}", encoding="utf-8")
            (root / "reports" / "war_room" / "room.md").write_text("# War Room\n", encoding="utf-8")
            (root / "memory" / "war_room_execution" / "latest.json").write_text(
                json.dumps(
                    {
                        "mode": "war_room_execution_queue",
                        "summary": {"task_count": 18, "open_count": 10, "blocked_count": 8, "approval_required_count": 7},
                        "tasks": [{"role": "research_analyst", "source": "search_confirmation.government_confirmation"}],
                    }
                ),
                encoding="utf-8",
            )
            (root / "memory" / "war_room_execution" / "queue.json").write_text("{}", encoding="utf-8")
            (root / "reports" / "war_room_execution" / "queue.md").write_text("# Queue\n", encoding="utf-8")

            env = {
                "V11_MISSION_CONTROL_DIR": str(root / "reports" / "mission_control"),
                "V11_MISSION_CONTROL_MEMORY_DIR": str(root / "memory" / "mission_control"),
            }
            with patch.dict(os.environ, env, clear=False):
                result = write_mission_control(root)

        self.assertTrue(result["ok"])
        snapshot = result["snapshot"]
        self.assertEqual(snapshot["status"], "human_review_required")
        self.assertTrue(snapshot["capability_evidence"]["customs_information_domain"])
        self.assertEqual(snapshot["capability_evidence"]["benchmark_questions"], 50)
        self.assertIn("evidence_dossiers", snapshot["capability_evidence"])
        self.assertIn("action_boards", snapshot["capability_evidence"])
        self.assertIn("team_responses", snapshot["capability_evidence"])
        self.assertEqual(snapshot["capability_evidence"]["war_rooms"], 1)
        self.assertEqual(snapshot["capability_evidence"]["latest_war_room_mode"], "industry_war_room")
        self.assertEqual(snapshot["capability_evidence"]["latest_war_room_score"], 91)
        self.assertEqual(snapshot["capability_evidence"]["latest_war_room_roles"], 6)
        self.assertEqual(snapshot["capability_evidence"]["latest_war_room_search_gate"], "lead_only")
        self.assertEqual(snapshot["capability_evidence"]["war_room_execution_queues"], 1)
        self.assertEqual(snapshot["capability_evidence"]["latest_war_room_queue_tasks"], 18)
        self.assertEqual(snapshot["capability_evidence"]["latest_war_room_queue_blocked"], 8)
        self.assertEqual(snapshot["capability_evidence"]["search_confirmation_gate"]["status"], "lead_only")
        self.assertFalse(snapshot["capability_evidence"]["search_confirmation_gate"]["can_create_confirmed_project_record"])
        self.assertEqual(snapshot["capability_evidence"]["promotion_readiness_gate"]["weak_lead_status"], "lead_only")
        self.assertEqual(snapshot["capability_evidence"]["promotion_readiness_gate"]["official_project_status"], "draft_promotion_ready")
        self.assertFalse(snapshot["capability_evidence"]["promotion_readiness_gate"]["external_use_default"])
        self.assertIn("project_library_summary", snapshot["capability_evidence"])
        self.assertEqual(snapshot["priority_queue"][0]["project"], "Kazakhstan Logistics")
        self.assertIn("v11 Mission Control", render_mission_control(snapshot))

    def test_api_mission_control_returns_operating_brief(self) -> None:
        response = TestClient(app).get("/v1/mission-control")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertIn("snapshot", data)
        self.assertIn("capability_evidence", data["snapshot"])

    def test_v11_search_knowledge_and_benchmark_are_readable_vertical_systems(self) -> None:
        search_response = TestClient(app).post("/v1/search", json={"query": "哈萨克斯坦工程贸易 海关 招商 视频"})
        self.assertEqual(search_response.status_code, 200)
        search_data = search_response.json()
        categories = {item["category"] for item in search_data["enrichment"]["category_queries"]}
        self.assertIn("government_confirmation", categories)
        self.assertIn("customs_trade", categories)
        self.assertIn("public_attention", categories)
        self.assertTrue(any(item["required"] and "site:" in item["query"] for item in search_data["project_search_plan"]))
        self.assertIn("source_readiness", search_data)
        self.assertIn("project_confirmation_gate", search_data)
        self.assertEqual(search_data["project_confirmation_gate"]["status"], "lead_only")
        self.assertFalse(search_data["project_confirmation_gate"]["can_create_confirmed_project_record"])
        self.assertIn("政府官网或官方采购页面", " ".join(search_data["project_confirmation_gate"]["required_before_confirmed_project"]))
        self.assertIn("Final answers must separate verified facts", search_data["answer_rule"])
        self.assertEqual(search_data["evidence_execution_brief"]["mode"], "search_to_execution_brief")
        self.assertEqual(search_data["evidence_execution_brief"]["verification_status"], "search_plan_only")
        self.assertIn("project_confirmation_gate", search_data["evidence_execution_brief"])
        self.assertIn("Attach collected official evidence", " ".join(search_data["evidence_execution_brief"]["project_execution"]["next_actions"]))
        self.assertIn("报价", search_data["evidence_execution_brief"]["blocked_actions"])
        self.assertIn("search_expansion", search_data)
        self.assertIn("source_status", search_data)
        self.assertIn("result_categories", search_data)
        self.assertIn("candidate_projects", search_data)
        self.assertIn("project_brief_draft", search_data)
        self.assertIn("Kazakhstan EPC project", search_data["search_expansion"]["english_terms"])
        self.assertTrue(search_data["search_expansion"]["russian_terms"])
        self.assertTrue(any(item["source"] == "Bing" for item in search_data["source_status"]))
        self.assertTrue(all("reason" in item and "next_action" in item for item in search_data["source_status"]))
        self.assertIn("official_sources", search_data["result_categories"])
        self.assertIn("social_video", search_data["result_categories"])
        self.assertTrue(search_data["candidate_projects"])
        self.assertEqual(search_data["candidate_projects"][0]["official_source_status"], "search_plan_only")
        self.assertEqual(search_data["candidate_projects"][0]["project_record_status"], "candidate_project")
        self.assertFalse(search_data["candidate_projects"][0]["verified_project_allowed"])
        self.assertEqual(search_data["project_brief_draft"]["status"], "draft_not_approved_for_external_use")
        self.assertIn("official evidence", search_data["project_brief_draft"]["risk_notice"])

        with tempfile.TemporaryDirectory() as temp:
            env = {
                "V11_KNOWLEDGE_BASE_PATH": str(Path(temp) / "knowledge.json"),
                "V11_BENCHMARK_PATH": str(Path(temp) / "benchmark.json"),
            }
            with patch.dict(os.environ, env, clear=False):
                knowledge = build_industry_knowledge_base()
                benchmark = build_v11_benchmark()

        self.assertIn("quality_rule", knowledge["data"])
        self.assertIn("customs_information", knowledge["data"]["domains"])
        self.assertEqual(benchmark["data"]["question_count"], 50)
        self.assertTrue(any("如何确认哈萨克斯坦进口矿山设备" in item["question"] for item in benchmark["data"]["questions"]))
        self.assertIn("Doubao", benchmark["data"]["questions"][0]["compare_targets"])
        self.assertIn("Yuanbao", benchmark["data"]["questions"][0]["compare_targets"])
        serialized = json.dumps(benchmark["data"], ensure_ascii=False)
        self.assertNotIn("濡備綍", serialized)
        self.assertNotIn("鍝堣惃", serialized)
        self.assertIn("v11 wins only when", benchmark["data"]["winner_rule"])


if __name__ == "__main__":
    unittest.main()
