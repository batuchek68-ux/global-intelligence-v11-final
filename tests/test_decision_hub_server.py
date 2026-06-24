from __future__ import annotations

import json
import shutil
import subprocess
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
REQUEST_TIMEOUT = 60


class DecisionHubServerTests(unittest.TestCase):
    def _start_server(self, port: int) -> subprocess.Popen:
        script = ROOT / "apps" / "decision-hub" / "server.ps1"
        powershell = shutil.which("pwsh") or shutil.which("powershell.exe")
        if not powershell:
            self.skipTest("PowerShell runtime is not available on this runner")
        process = subprocess.Popen(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-Port",
                str(port),
            ],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.time() + 20
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                with urlopen(f"http://127.0.0.1:{port}/", timeout=2) as response:
                    if response.status == 200:
                        return process
            except Exception as exc:  # pragma: no cover - startup timing
                last_error = exc
                time.sleep(0.5)
        process.terminate()
        raise AssertionError(f"Decision Hub did not start: {last_error}")

    def test_local_search_returns_v11_classified_plan(self) -> None:
        port = 8898
        process = self._start_server(port)
        try:
            payload = json.dumps({"query": "哈萨克斯坦工程贸易 海关 招商 视频", "sources": []}).encode("utf-8")
            request = Request(
                f"http://127.0.0.1:{port}/api/search",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))

            self.assertTrue(data["ok"])
            categories = {item["category"] for item in data["enrichment"]["category_queries"]}
            self.assertIn("government_confirmation", categories)
            self.assertIn("customs_trade", categories)
            self.assertIn("public_attention", categories)
            self.assertIn("source_readiness", data)
            self.assertIn("project_confirmation_gate", data)
            self.assertEqual(data["project_confirmation_gate"]["status"], "lead_only")
            self.assertFalse(data["project_confirmation_gate"]["can_create_confirmed_project_record"])
            self.assertTrue(any(item["required"] and "site:" in item["query"] for item in data["project_search_plan"]))
            self.assertIn("Final answers must separate verified facts", data["answer_rule"])
            self.assertEqual(data["evidence_execution_brief"]["mode"], "search_to_execution_brief")
            self.assertEqual(data["evidence_execution_brief"]["project_execution"]["record_status"], "lead_only")
            self.assertIn("报价", data["evidence_execution_brief"]["blocked_actions"])
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
                process.kill()

    def test_project_pipeline_endpoint_returns_execution_package(self) -> None:
        port = 8897
        process = self._start_server(port)
        try:
            payload = json.dumps({"topic": "哈萨克斯坦工程贸易", "country": "Kazakhstan", "evidence": []}).encode("utf-8")
            request = Request(
                f"http://127.0.0.1:{port}/api/project/pipeline",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))

            self.assertTrue(data["ok"])
            self.assertEqual(data["mode"], "project_intelligence_pipeline")
            self.assertIn("search_plan", data)
            self.assertIn("project_library", data)
            self.assertIn("action_board", data)
            self.assertIn("feasibility_report", data)
            self.assertIn("external outreach", data["blocked_actions"])
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
                process.kill()

    def test_project_library_endpoint_returns_classified_summary(self) -> None:
        port = 8892
        process = self._start_server(port)
        try:
            request = Request(f"http://127.0.0.1:{port}/api/projects/library", method="GET")
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))

            self.assertTrue(data["ok"])
            self.assertIn("summary", data)
            self.assertIn("categories", data)
            self.assertIn("under_construction", data["categories"])
            self.assertIn("planned", data["categories"])
            self.assertIn("unconfirmed", data["categories"])
            self.assertIn("official_ready", data)
            self.assertIn("needs_evidence", data)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
                process.kill()

    def test_team_execute_endpoint_returns_six_role_package(self) -> None:
        port = 8896
        process = self._start_server(port)
        try:
            payload = json.dumps(
                {
                    "objective": "Kazakhstan EPC customs investment promotion video execution",
                    "country": "Kazakhstan",
                    "industries": ["mining", "logistics"],
                    "evidence": [],
                    "audience": "internal",
                }
            ).encode("utf-8")
            request = Request(
                f"http://127.0.0.1:{port}/api/team/execute",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))

            self.assertTrue(data["ok"])
            roles = {item["role"] for item in data["team_roles"]}
            self.assertIn("trade_lead", roles)
            self.assertIn("research_analyst", roles)
            self.assertIn("investment_promotion_lead", roles)
            self.assertIn("video_media_producer", roles)
            self.assertIn("project_manager", roles)
            self.assertIn("risk_approval_officer", roles)
            self.assertTrue(data["deliverables"])
            self.assertTrue(data["search_plan"]["video_platform_searches"])
            self.assertTrue(data["risk"]["needs_human_approval"])
            self.assertIn("public publishing", data["risk"]["blocked_actions"])
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
                process.kill()

    def test_video_center_endpoint_returns_draft_production_pack(self) -> None:
        port = 8891
        process = self._start_server(port)
        try:
            payload = json.dumps(
                {
                    "topic": "Kazakhstan engineering trade investment project",
                    "country": "Kazakhstan",
                    "industry": "logistics",
                }
            ).encode("utf-8")
            request = Request(
                f"http://127.0.0.1:{port}/api/video/center",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))

            self.assertTrue(data["ok"])
            self.assertTrue(data["video_keywords"])
            self.assertTrue(data["platform_searches"])
            platforms = {item["platform"] for item in data["platform_searches"]}
            self.assertIn("YouTube", platforms)
            self.assertIn("TikTok", platforms)
            self.assertIn("Douyin", platforms)
            self.assertIn("Video drafts are internal", data["rules"][0])
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
                process.kill()

    def test_intelligence_brief_endpoint_returns_internal_draft(self) -> None:
        port = 8890
        process = self._start_server(port)
        try:
            payload = json.dumps(
                {
                    "topic": "Kazakhstan engineering trade investment pipeline",
                    "country": "Kazakhstan",
                    "industry": "logistics",
                    "items": [
                        {
                            "title": "Government announces billion dollar logistics tender with high public attention",
                            "summary": "Minister policy update, tender, EPC contractor, investment financing and YouTube trending analysis",
                            "source_type": "government",
                        }
                    ],
                }
            ).encode("utf-8")
            request = Request(
                f"http://127.0.0.1:{port}/api/intelligence/brief",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))

            self.assertTrue(data["ok"])
            self.assertIn("DRAFT - internal intelligence", data["content"])
            self.assertTrue(data["search_system"]["categories"])
            buckets = data["classified"]["buckets"]
            self.assertTrue(buckets["political_impact"])
            self.assertTrue(buckets["high_attention"])
            self.assertTrue(buckets["project_critical"])
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
                process.kill()

    def test_quality_score_and_compare_endpoints_work_from_desktop(self) -> None:
        port = 8895
        process = self._start_server(port)
        try:
            score_payload = json.dumps(
                {
                    "question": "如何确认进口设备海关信息？",
                    "answer": "Use official customs source URL and date, verify HS code, tariff, customs valuation, risk, approval boundary, and next step checklist.",
                    "evidence": [{"source_type": "official", "url": "https://customs.example"}],
                }
            ).encode("utf-8")
            score_request = Request(
                f"http://127.0.0.1:{port}/api/answers/score",
                data=score_payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(score_request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                score = json.loads(response.read().decode("utf-8"))
            self.assertTrue(score["ok"])
            self.assertGreaterEqual(score["overall_score"], 70)
            self.assertIn("risk_judgment", score["dimensions"])

            compare_payload = json.dumps(
                {
                    "question": "如何确认进口设备海关信息？",
                    "answers": {
                        "v11": "Check official customs URL and date, verify HS code, tariff, customs valuation, documents, risk, approval boundary, and next step checklist.",
                        "Doubao": "Search online and ask a customs expert.",
                        "Yuanbao": "Prepare import documents and check the policy.",
                    },
                }
            ).encode("utf-8")
            compare_request = Request(
                f"http://127.0.0.1:{port}/api/benchmark/compare",
                data=compare_payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(compare_request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                comparison = json.loads(response.read().decode("utf-8"))
            self.assertTrue(comparison["ok"])
            self.assertEqual(comparison["ranked"][0]["name"], "v11")
            self.assertIn("Doubao", comparison["scores"])
            self.assertIn("Yuanbao", comparison["scores"])
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
                process.kill()

    def test_team_response_endpoint_works_from_desktop(self) -> None:
        port = 8899
        process = self._start_server(port)
        try:
            payload = json.dumps(
                {
                    "question": "如何确认哈萨克斯坦工程贸易项目的海关信息、项目负责人、招商价值和视频传播方案？",
                    "country": "Kazakhstan",
                    "industries": ["infrastructure", "mining", "logistics"],
                    "evidence": [
                        {
                            "title": "Official procurement page",
                            "url": "https://goszakup.gov.kz/example-project",
                            "source_type": "government",
                            "snippet": "Official source describes owner, tender status, customs documents and engineering scope.",
                        }
                    ],
                }
            ).encode("utf-8")
            request = Request(
                f"http://127.0.0.1:{port}/api/team/response",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))

            pack = data["pack"]
            self.assertTrue(data["ok"])
            self.assertEqual(pack["mode"], "team_response_pack")
            self.assertGreaterEqual(len(pack["team_roles"]), 6)
            self.assertIn("国际贸易负责人", {item["label"] for item in pack["team_roles"]})
            self.assertIn("风控审批负责人", {item["label"] for item in pack["team_roles"]})
            self.assertTrue(pack["approval_boundary"]["draft_only"])
            self.assertGreaterEqual(pack["quality_score"]["overall_score"], 70)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
                process.kill()

    def test_war_room_endpoint_works_from_desktop(self) -> None:
        port = 8898
        process = self._start_server(port)
        try:
            payload = json.dumps(
                {
                    "objective": "Kazakhstan engineering trade project customs investment promotion video",
                    "country": "Kazakhstan",
                    "industries": ["infrastructure", "logistics"],
                    "evidence": [
                        {
                            "title": "Official procurement page",
                            "url": "https://goszakup.gov.kz/example-project",
                            "source_type": "government",
                            "snippet": "Official source describes owner, tender status, customs documents and engineering scope.",
                        }
                    ],
                }
            ).encode("utf-8")
            request = Request(
                f"http://127.0.0.1:{port}/api/war-room/build",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))

            room = data["war_room"]
            self.assertTrue(data["ok"])
            self.assertEqual(room["mode"], "industry_war_room")
            self.assertEqual(room["search_confirmation"]["project_confirmation_gate"]["status"], "lead_only")
            self.assertGreaterEqual(len(room["team"]["roles"]), 6)
            self.assertTrue(room["video_center"]["platform_searches"])
            self.assertFalse(room["approval_boundary"]["external_use_allowed"])
            self.assertGreaterEqual(room["quality_score"]["overall_score"], 70)

            queue_request = Request(f"http://127.0.0.1:{port}/api/war-room/execution-queue", method="GET")
            with urlopen(queue_request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                queue_data = json.loads(response.read().decode("utf-8"))
            self.assertTrue(queue_data["ok"])
            self.assertEqual(queue_data["queue"]["mode"], "war_room_execution_queue")
            self.assertGreaterEqual(queue_data["queue"]["summary"]["task_count"], 12)
            self.assertIn("Read-only queue view", queue_data["note"])
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
                process.kill()

    def test_social_reply_draft_endpoint_blocks_sending(self) -> None:
        port = 8894
        process = self._start_server(port)
        try:
            analyze_payload = json.dumps(
                {
                    "channel": "enterprise_wechat",
                    "message": "Please confirm the government project developer, price, payment and delivery date.",
                    "authorization": {"scope": "draft_only"},
                    "audience": "external",
                }
            ).encode("utf-8")
            analyze_request = Request(
                f"http://127.0.0.1:{port}/api/social/analyze",
                data=analyze_payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(analyze_request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                assessment = json.loads(response.read().decode("utf-8"))
            self.assertEqual(assessment["action"], "draft_only")
            self.assertTrue(assessment["needs_human_approval"])
            self.assertEqual(assessment["risk_level"], "high")

            draft_payload = json.dumps(
                {
                    "channel": "enterprise_wechat",
                    "recipient": "partner",
                    "message": "Please confirm the government project developer, price, payment and delivery date.",
                    "authorization": {"scope": "draft_only"},
                    "audience": "external",
                }
            ).encode("utf-8")
            draft_request = Request(
                f"http://127.0.0.1:{port}/api/social/reply-draft",
                data=draft_payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(draft_request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                draft = json.loads(response.read().decode("utf-8"))
            self.assertTrue(draft["ok"])
            self.assertFalse(draft["sent"])
            self.assertEqual(draft["assessment"]["action"], "draft_only")
            self.assertTrue(draft["approval_checklist"])
            self.assertIn("DRAFT - Not approved for sending", draft["draft"]["message"])
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
                process.kill()

    def test_evidence_verify_endpoint_returns_dossier(self) -> None:
        port = 8893
        process = self._start_server(port)
        try:
            payload = json.dumps(
                {
                    "claim": "Kazakhstan logistics EPC project owner and customs documents are confirmed",
                    "project": "Kazakhstan logistics hub",
                    "country": "Kazakhstan",
                    "evidence": [
                        {
                            "title": "Government procurement project page",
                            "url": "https://goszakup.gov.kz/example-project",
                            "source_type": "procurement",
                            "snippet": "Official procurement page describes project owner, EPC contractor scope and customs documents.",
                        }
                    ],
                }
            ).encode("utf-8")
            request = Request(
                f"http://127.0.0.1:{port}/api/evidence/verify",
                data=payload,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                self.assertEqual(response.status, 200)
                data = json.loads(response.read().decode("utf-8"))

            self.assertTrue(data["ok"])
            self.assertEqual(data["dossier"]["verification_status"], "officially_supported")
            self.assertGreaterEqual(data["dossier"]["confidence"], 90)
            self.assertEqual(data["dossier"]["summary"]["official_sources"], 1)
            self.assertIn("report_path", data)
            self.assertIn("human_review", {item["source"] for item in data["dossier"]["next_verification_steps"]})
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - cleanup fallback
                process.kill()


if __name__ == "__main__":
    unittest.main()
