from __future__ import annotations

import unittest
import json
import os
import subprocess
import tempfile
import urllib.error
from pathlib import Path

import core.decision as decision_module
import workflows.daily_job as daily_job_module
from comm.github_issue import build_decision_receipt, maybe_close_issue
from workflows.preflight_check import check as preflight_check
from workflows.cloud_acceptance import build_acceptance_status, render_acceptance_report, run_acceptance
import workflows.trigger_cloud_acceptance as trigger_module
from workflows.trigger_cloud_acceptance import WORKFLOW_FILE, trigger_cloud_acceptance
from workflows.upload_and_trigger_cloud import upload_and_trigger, uploadable_files
from workflows.create_repo_upload_and_trigger import create_upload_and_trigger, ensure_repository
from workflows.cloud_connection_check import build_connection_check
import workflows.cloud_connection_check as connection_module
import workflows.cloud_config as cloud_config_module
from workflows.cloud_config import configured_repository, configured_token_info, load_cloud_config, repository_from_git_config, repository_from_remote_url, token_from_gh_cli, valid_repository_name
from workflows.cloud_run import build_cloud_run
from workflows.cloud_test_status import build_status as build_cloud_test_status, render_status as render_cloud_test_status
from workflows.persist_state import STATE_PATHS
import workflows.persist_state as persist_state_module
from workflows.ensure_labels import LABELS, ensure_labels
from workflows.prepare_release import ROOT as RELEASE_ROOT, collect_files
from workflows.publish_summary import publish_summary
from workflows.watchdog import build_watchdog_status, run_watchdog
from core.decision import normalize_project_name, parse_owner_reply, resolve_major_matter
from core.executor import build_execution_record
from core.business_flow import build_business_flow
from core.judge import judge_project
from core.models import Project
from core.operator import classify_matter
from core.planner import plan_actions
from core.report import build_headquarters_report, build_owner_inbox
from comm.notification import approval_message, notify_major_matter
from intelligence.kazakhstan_xinjiang_monitor import build_monitoring_summary


class OperatingCycleTests(unittest.TestCase):
    def test_high_risk_project_requires_approval(self) -> None:
        project = Project(
            path="demo.md",
            title="Demo",
            country="Indonesia",
            counterparty="Owner",
            amount=250000,
            latest_communication="payment and customs are unclear",
            risks=["payment", "customs"],
            next_decision="commit delivery date",
        )
        judgment = judge_project(project)
        self.assertTrue(judgment.needs_approval)
        self.assertEqual(judgment.level, "high")

    def test_planner_adds_approval_action(self) -> None:
        project = Project(path="demo.md", title="Demo")
        judgment = judge_project(Project(path="demo.md", title="Demo", amount=200000))
        actions = plan_actions(project, judgment)
        self.assertIn("approval", actions[0].lower())

    def test_low_risk_project_is_autonomous(self) -> None:
        project = Project(
            path="demo.md",
            title="Small reversible task",
            amount=1000,
            latest_communication="internal data collection only",
        )
        judgment = judge_project(project)
        classification = classify_matter(project, judgment)
        self.assertFalse(classification["is_major_matter"])
        self.assertEqual(classification["mode"], "autonomous_execution")

    def test_execution_record_for_autonomous_project(self) -> None:
        project = Project(
            path="demo.md",
            title="Internal",
            amount=100,
            latest_communication="internal reversible cleanup confirmed",
        )
        judgment = judge_project(project)
        classification = classify_matter(project, judgment)
        record = build_execution_record(project, judgment, ["Do safe step"], classification)
        self.assertEqual(record["status"], "autonomous_executed")
        self.assertFalse(record["requires_owner"])

    def test_owner_reply_parser_accepts_slash_commands(self) -> None:
        parsed = parse_owner_reply("/approve proceed with staged commitment")
        self.assertTrue(parsed["valid"])
        self.assertEqual(parsed["decision"], "approve")
        self.assertEqual(parsed["notes"], "proceed with staged commitment")

    def test_resolve_major_matter_writes_continuation(self) -> None:
        original_root = decision_module.ROOT
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            outbox = temp_root / "comm" / "outbox"
            outbox.mkdir(parents=True)
            (outbox / "demo-port-logistics-modernization.json").write_text(
                json.dumps({"project": "Demo Port Logistics Modernization", "status": "waiting"}),
                encoding="utf-8",
            )
            decision_module.ROOT = temp_root
            try:
                result = resolve_major_matter(
                    "[Major Matter] Demo Port Logistics Modernization requires owner decision",
                    "/revise only commit after customs broker confirms timeline",
                    source="unit-test",
                )
            finally:
                decision_module.ROOT = original_root
        self.assertTrue(result["resolved"])
        self.assertEqual(result["decision"], "revise")
        self.assertIn("continuation_path", result)

    def test_normalize_project_name_from_issue_title(self) -> None:
        self.assertEqual(
            normalize_project_name("[Major Matter] Demo Port Logistics Modernization requires owner decision"),
            "Demo Port Logistics Modernization",
        )

    def test_daily_cycle_preserves_resolved_major_matter(self) -> None:
        original_root = daily_job_module.ROOT
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            outbox_dir = temp_root / "comm" / "outbox"
            outbox_dir.mkdir(parents=True)
            (outbox_dir / "demo.json").write_text(
                json.dumps(
                    {
                        "project": "Demo",
                        "status": "resolved",
                        "owner_decision": "approve",
                        "owner_notes": "staged only",
                        "resolved_at": "2026-06-21T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            project = Project(
                path="demo.md",
                title="Demo",
                country="Indonesia",
                counterparty="Owner",
                amount=250000,
                stage="proposal",
                latest_communication="payment and customs are unclear",
                risks=["payment", "customs", "compliance"],
                next_decision="commit delivery date",
            )
            daily_job_module.ROOT = temp_root
            daily_job_module.__dict__["ensure_dirs"] = lambda: None
            try:
                summary = daily_job_module.run_daily_cycle(projects=[project])
                ticket = json.loads((outbox_dir / "demo.json").read_text(encoding="utf-8"))
                self.assertTrue((temp_root / "memory" / "knowledge_base" / "industry_knowledge.json").is_file())
                self.assertTrue((temp_root / "memory" / "benchmark" / "v11_benchmark_50.json").is_file())
                self.assertTrue((temp_root / "memory" / "evidence" / "latest.json").is_file())
                self.assertTrue((temp_root / "reports" / "evidence" / "latest.md").is_file())
                self.assertTrue((temp_root / "memory" / "action_boards" / "latest.json").is_file())
                self.assertTrue((temp_root / "reports" / "action_boards" / "latest.md").is_file())
                self.assertTrue((temp_root / "memory" / "team_responses" / "latest.json").is_file())
                self.assertTrue((temp_root / "reports" / "team_responses" / "latest.md").is_file())
                self.assertTrue((temp_root / "memory" / "war_room" / "latest.json").is_file())
                self.assertTrue((temp_root / "reports" / "war_room" / "latest.md").is_file())
                self.assertTrue((temp_root / "memory" / "intelligence" / "keyword_bank.json").is_file())
                self.assertTrue((temp_root / "reports" / "benchmark" / "daily_answer_score.json").is_file())
                self.assertIn("monitoring", summary)
                self.assertTrue((temp_root / "projects" / "library" / "kazakhstan_xinjiang_projects.json").is_file())
                self.assertTrue((temp_root / "memory" / "monitoring" / "kazakhstan_xinjiang_daily.json").is_file())
                self.assertTrue((temp_root / "reports" / "kazakhstan_xinjiang_monitoring.md").is_file())
                self.assertGreater(len(list((temp_root / "reports" / "team_execution").glob("*.md"))), 0)
                self.assertGreater(len(list((temp_root / "reports" / "intelligence_briefs").glob("*.md"))), 0)
                self.assertGreater(len(list((temp_root / "reports" / "video_center").glob("*.json"))), 0)
            finally:
                daily_job_module.ROOT = original_root
                daily_job_module.__dict__["ensure_dirs"] = __import__("core.storage", fromlist=["ensure_dirs"]).ensure_dirs
        self.assertEqual(ticket["status"], "resolved")
        self.assertEqual(ticket["owner_decision"], "approve")
        self.assertEqual(summary["resolved_major_matter_count"], 1)
        capabilities = summary["v11_capabilities"]
        self.assertTrue(capabilities["knowledge_base"]["has_customs_information"])
        self.assertGreaterEqual(capabilities["benchmark"]["question_count"], 50)
        self.assertGreaterEqual(capabilities["answer_scoring"]["overall_score"], 70)
        self.assertGreaterEqual(capabilities["evidence_verification"]["dossier_count"], 1)
        self.assertGreaterEqual(capabilities["action_boards"]["board_count"], 1)
        self.assertGreaterEqual(capabilities["team_response"]["overall_score"], 70)
        self.assertGreaterEqual(capabilities["war_room"]["overall_score"], 70)
        self.assertGreaterEqual(capabilities["war_room"]["role_count"], 6)
        self.assertEqual(capabilities["war_room"]["search_gate"], "lead_only")
        self.assertFalse(capabilities["war_room"]["external_use_allowed"])
        self.assertEqual(capabilities["team_execution"]["package_count"], 1)
        self.assertEqual(capabilities["mission_control"]["waiting_for_owner"], 0)
        self.assertTrue(Path(capabilities["mission_control"]["report_path"]).name.endswith(".md"))

    def test_headquarters_report_names_command_model(self) -> None:
        report = build_headquarters_report(
            {
                "project_count": 1,
                "case_count": 0,
                "major_matter_count": 0,
                "resolved_major_matter_count": 0,
                "cases": [],
            }
        )
        self.assertIn("GitHub: cloud AI headquarters", report)
        self.assertIn("Codex: 24h autonomous executive", report)
        self.assertIn("Owner: decides only major matters", report)

    def test_owner_inbox_has_no_decision_message(self) -> None:
        inbox = build_owner_inbox({"cases": []})
        self.assertIn("No Owner Decisions Required", inbox)

    def test_owner_inbox_includes_reply_templates(self) -> None:
        inbox = build_owner_inbox(
            {
                "cases": [
                    {
                        "project": {"title": "Demo", "country": "ID", "counterparty": "Owner"},
                        "judgment": {
                            "level": "high",
                            "score": 88,
                            "triggers": ["payment"],
                            "recommendation": "Review before commitment.",
                        },
                        "classification": {"is_major_matter": True},
                    }
                ]
            }
        )
        self.assertIn("/approve proceed with this plan", inbox)
        self.assertIn("/reject reason for rejection", inbox)
        self.assertIn("/revise conditions for continuing", inbox)

    def test_preflight_passes_current_repository(self) -> None:
        result = preflight_check()
        self.assertTrue(result["ok"], result)

    def test_persist_state_tracks_operating_paths(self) -> None:
        self.assertIn("memory", STATE_PATHS)
        self.assertIn("reports", STATE_PATHS)
        self.assertIn("comm/outbox", STATE_PATHS)
        self.assertIn("projects/library", STATE_PATHS)

    def test_kazakhstan_xinjiang_monitor_writes_daily_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            summary = build_monitoring_summary(temp_root)
            self.assertEqual(summary["project_count"], 5)
            self.assertFalse(summary["source_status"]["live_fetch"])
            self.assertTrue((temp_root / "reports" / "daily_logs" / f"{summary['date']}.md").is_file())
            self.assertTrue((temp_root / "reports" / "news_updates" / f"{summary['date']}.json").is_file())
            self.assertTrue((temp_root / "reports" / "project_library" / f"{summary['date']}.md").is_file())
            self.assertTrue((temp_root / "projects" / "library" / "kazakhstan_xinjiang_projects.json").is_file())
            self.assertTrue((temp_root / "memory" / "monitoring" / "customs_watch" / f"{summary['date']}.json").is_file())
            self.assertIn("DRAFT - Not approved for sending", (temp_root / "reports" / "news_updates" / f"{summary['date']}.md").read_text(encoding="utf-8"))

    def test_international_trade_workflow_uploads_project_library(self) -> None:
        workflow = (RELEASE_ROOT / ".github" / "workflows" / "international_trade_ops.yml").read_text(encoding="utf-8")
        self.assertIn("backend/projects/library/", workflow)

    def test_persist_state_pushes_to_github_ref_name(self) -> None:
        original_env = os.environ.get("GITHUB_REF_NAME")
        original_run = persist_state_module.run
        captured = {}

        def fake_run(command):
            captured["command"] = command
            return subprocess.CompletedProcess(command, 0, "", "")

        try:
            persist_state_module.run = fake_run
            os.environ["GITHUB_REF_NAME"] = "main"
            persist_state_module.push_state("main")
        finally:
            persist_state_module.run = original_run
            if original_env is None:
                os.environ.pop("GITHUB_REF_NAME", None)
            else:
                os.environ["GITHUB_REF_NAME"] = original_env
        self.assertEqual(captured["command"], ["git", "push", "origin", "HEAD:main"])

    def test_label_set_includes_owner_queue(self) -> None:
        self.assertIn("major-matter", LABELS)
        self.assertIn("owner-decision", LABELS)
        self.assertIn("autonomous", LABELS)

    def test_ensure_labels_skips_without_github_env(self) -> None:
        result = ensure_labels()
        self.assertFalse(result["ok"])

    def test_release_files_include_workflows(self) -> None:
        files = {path.relative_to(RELEASE_ROOT).as_posix() for path in collect_files()}
        self.assertIn(".github/workflows/international_trade_ops.yml", files)
        self.assertIn(".github/workflows/owner_decision.yml", files)
        self.assertIn(".github/workflows/watchdog.yml", files)
        self.assertIn(".github/workflows/cloud_acceptance.yml", files)
        self.assertIn("cloud.local.example.json", files)
        self.assertIn("cloud.env.example.ps1", files)
        self.assertIn("check-cloud-config.cmd", files)
        self.assertIn("check-cloud-config.ps1", files)
        self.assertIn("run-cloud-test.cmd", files)
        self.assertIn("run-cloud-test.ps1", files)
        self.assertIn("setup-cloud-test.ps1", files)
        self.assertIn("运行云端测试.cmd", files)
        self.assertIn("运行云端测试.ps1", files)
        self.assertIn("workflows/preflight_check.py", files)
        self.assertIn("workflows/cloud_acceptance.py", files)
        self.assertIn("workflows/trigger_cloud_acceptance.py", files)
        self.assertIn("workflows/upload_and_trigger_cloud.py", files)
        self.assertIn("workflows/create_repo_upload_and_trigger.py", files)
        self.assertIn("workflows/cloud_connection_check.py", files)
        self.assertIn("workflows/cloud_config.py", files)
        self.assertIn("workflows/cloud_run.py", files)
        self.assertIn("workflows/cloud_test_status.py", files)
        self.assertIn("docs/github-deployment-runbook.md", files)
        self.assertIn("docs/cloud-run.md", files)
        self.assertIn("docs/github-token-setup.md", files)

    def test_cloud_local_example_is_packaged_and_real_config_ignored(self) -> None:
        ignored = (RELEASE_ROOT / ".gitignore").read_text(encoding="utf-8")
        config = load_cloud_config(RELEASE_ROOT / "cloud.local.example.json")
        self.assertIn("cloud.local.json", ignored)
        self.assertIn("cloud.env.ps1", ignored)
        self.assertTrue(config["exists"])
        self.assertEqual(config["repository"], "owner/repository")

    def test_cloud_repository_name_validation(self) -> None:
        self.assertTrue(valid_repository_name("octocat/international-trade-ai"))
        self.assertFalse(valid_repository_name(None))
        self.assertFalse(valid_repository_name("repo-without-owner"))
        self.assertFalse(valid_repository_name("owner/"))
        self.assertFalse(valid_repository_name("/repository"))
        self.assertFalse(valid_repository_name("owner/repository/extra"))
        self.assertFalse(valid_repository_name("owner/repository"))
        self.assertFalse(valid_repository_name("yourname/international-trade-ai"))
        self.assertFalse(valid_repository_name("你的GitHub用户名/仓库名"))

    def test_cloud_repository_can_be_read_from_git_remote(self) -> None:
        self.assertEqual(repository_from_remote_url("https://github.com/octocat/international-trade-ai.git"), "octocat/international-trade-ai")
        self.assertEqual(repository_from_remote_url("git@github.com:octocat/international-trade-ai.git"), "octocat/international-trade-ai")
        self.assertEqual(repository_from_remote_url("ssh://git@github.com/octocat/international-trade-ai.git"), "octocat/international-trade-ai")
        self.assertIsNone(repository_from_remote_url("https://example.com/owner/repository.git"))

    def test_cloud_repository_can_be_read_from_git_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "config"
            config.write_text(
                '[remote "origin"]\n'
                "\turl = git@github.com:octocat/international-trade-ai.git\n",
                encoding="utf-8",
            )
            self.assertEqual(repository_from_git_config(config), "octocat/international-trade-ai")

    def test_cloud_token_can_be_read_from_gh_cli(self) -> None:
        original_which = cloud_config_module.shutil.which
        original_run = cloud_config_module.subprocess.run

        class Result:
            returncode = 0
            stdout = "gh-token\n"

        cloud_config_module.shutil.which = lambda name: "gh" if name == "gh" else None
        cloud_config_module.subprocess.run = lambda *args, **kwargs: Result()
        try:
            self.assertEqual(token_from_gh_cli(), "gh-token")
            self.assertEqual(configured_token_info()[1], "gh-cli")
        finally:
            cloud_config_module.shutil.which = original_which
            cloud_config_module.subprocess.run = original_run

    def test_cloud_token_prefers_environment_value(self) -> None:
        self.assertEqual(configured_token_info("env-token"), ("env-token", "environment"))

    def test_cloud_launchers_generate_status_report_on_missing_config(self) -> None:
        run_launcher = (RELEASE_ROOT / "run-cloud-test.ps1").read_text(encoding="utf-8")
        setup_launcher = (RELEASE_ROOT / "setup-cloud-test.ps1").read_text(encoding="utf-8")
        check_launcher = (RELEASE_ROOT / "check-cloud-config.ps1").read_text(encoding="utf-8")
        self.assertIn("python workflows\\cloud_test_status.py", run_launcher)
        self.assertIn("Test-RepositoryName", run_launcher)
        self.assertIn("real GitHub owner/repository", run_launcher)
        self.assertIn("python workflows\\cloud_test_status.py", setup_launcher)
        self.assertIn("python workflows\\cloud_connection_check.py", check_launcher)
        self.assertIn("python workflows\\cloud_test_status.py", check_launcher)
        self.assertIn("SaveRepository", setup_launcher)
        self.assertIn("[string]$Repository", setup_launcher)
        self.assertIn("Test-RepositoryName", setup_launcher)
        self.assertIn("real GitHub owner/repository", setup_launcher)
        self.assertIn("cloud.local.json", setup_launcher)

    def test_watchdog_workflow_persists_state(self) -> None:
        workflow = (RELEASE_ROOT / ".github" / "workflows" / "watchdog.yml").read_text(encoding="utf-8")
        self.assertIn("contents: write", workflow)
        self.assertIn("python workflows/persist_state.py", workflow)

    def test_cloud_acceptance_workflow_runs_full_chain(self) -> None:
        workflow = (RELEASE_ROOT / ".github" / "workflows" / "cloud_acceptance.yml").read_text(encoding="utf-8")
        self.assertIn("python workflows/preflight_check.py", workflow)
        self.assertIn("python -m unittest discover -s tests", workflow)
        self.assertIn("python workflows/daily_job.py", workflow)
        self.assertIn("python workflows/watchdog.py", workflow)
        self.assertIn("python workflows/cloud_acceptance.py", workflow)
        self.assertIn("python workflows/persist_state.py", workflow)

    def test_codex_autonomous_repair_workflow_exists(self) -> None:
        workflow = (RELEASE_ROOT / ".github" / "workflows" / "codex_autonomous_repair.yml").read_text(encoding="utf-8")
        self.assertIn("Codex Autonomous Repair", workflow)
        self.assertIn("python workflows/autonomous_repair.py", workflow)
        self.assertIn("python workflows/persist_state.py", workflow)

    def test_business_flow_covers_real_work_channels(self) -> None:
        project = Project(path="demo.md", title="Demo Trade Project", country="Kazakhstan")
        judgment = judge_project(project)
        flow = build_business_flow(project, judgment)
        coverage = flow["real_work_coverage"]
        self.assertIn("meeting_followup", coverage)
        self.assertIn("content_operations", coverage)
        self.assertIn("WeChat", coverage["meeting_followup"]["channels"])
        self.assertIn("QQ Meeting", coverage["meeting_followup"]["channels"])
        self.assertIn("Douyin", coverage["content_operations"]["platforms"])
        self.assertIn("TikTok", coverage["content_operations"]["platforms"])
        self.assertIn("YouTube", coverage["content_operations"]["platforms"])

    def test_notification_message_and_missing_secrets(self) -> None:
        ticket = {
            "project": "Demo",
            "country": "Kazakhstan",
            "counterparty": "Owner",
            "risk_level": "high",
            "risk_score": 88,
            "triggers": ["payment"],
            "question": "Approve next step?",
        }
        message = approval_message(ticket)
        self.assertIn("approval needed", message)
        self.assertIn("Demo", message)
        result = notify_major_matter(ticket)
        self.assertIn("enterprise_wechat", result)
        self.assertIn("feishu", result)
        self.assertIn("email", result)

    def test_trigger_cloud_acceptance_names_workflow_file(self) -> None:
        self.assertEqual(WORKFLOW_FILE, "cloud_acceptance.yml")

    def test_trigger_cloud_acceptance_reports_missing_workflow(self) -> None:
        original_get_workflow = trigger_module.get_workflow
        trigger_module.get_workflow = lambda repository, token: {"ok": False, "status": 404, "data": {}}
        try:
            result = trigger_cloud_acceptance("owner/repo", "token", wait=False)
        finally:
            trigger_module.get_workflow = original_get_workflow
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "workflow_lookup")

    def test_trigger_cloud_acceptance_extracts_failed_steps(self) -> None:
        original_request = trigger_module.github_request

        def fake_request(method, repository, path, token, payload=None):
            return 200, {
                "jobs": [
                    {
                        "name": "cloud-acceptance",
                        "status": "completed",
                        "conclusion": "failure",
                        "html_url": "https://example.test/job",
                        "steps": [
                            {"name": "Run tests", "number": 1, "status": "completed", "conclusion": "success"},
                            {"name": "Persist acceptance evidence", "number": 2, "status": "completed", "conclusion": "failure"},
                        ],
                    }
                ]
            }

        trigger_module.github_request = fake_request
        try:
            result = trigger_module.get_run_jobs("owner/repo", "token", 123)
        finally:
            trigger_module.github_request = original_request
        self.assertTrue(result["ok"])
        self.assertEqual(result["failed_steps"][0]["step"], "Persist acceptance evidence")

    def test_trigger_cloud_acceptance_reports_network_error(self) -> None:
        original_urlopen = trigger_module.urllib.request.urlopen
        trigger_module.urllib.request.urlopen = lambda *args, **kwargs: (_ for _ in ()).throw(
            urllib.error.URLError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred")
        )
        try:
            status, data = trigger_module.github_request("GET", "owner/repo", "/actions/runs/1", "token")
        finally:
            trigger_module.urllib.request.urlopen = original_urlopen
        self.assertEqual(status, 0)
        self.assertEqual(data["stage"], "network_error")

    def test_upload_and_trigger_requires_confirmation(self) -> None:
        result = upload_and_trigger("owner/repo", "token", confirm_upload=False)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "confirmation")

    def test_uploadable_files_include_cloud_workflows(self) -> None:
        files = {path.relative_to(RELEASE_ROOT).as_posix() for path in uploadable_files()}
        self.assertIn(".github/workflows/cloud_acceptance.yml", files)
        self.assertIn("workflows/upload_and_trigger_cloud.py", files)

    def test_upload_stops_on_bad_credentials(self) -> None:
        import workflows.upload_and_trigger_cloud as upload_module

        original_uploadable_files = upload_module.uploadable_files
        original_upload_file = upload_module.upload_file
        upload_module.uploadable_files = lambda: [RELEASE_ROOT / "README.md", RELEASE_ROOT / "requirements.txt"]
        upload_module.upload_file = lambda repository, token, path, branch, message_prefix: {
            "path": path.name,
            "ok": False,
            "status": 401,
            "action": "created",
            "details": {"message": "Bad credentials"},
        }
        try:
            result = upload_module.upload_repository("owner/repo", "token", "main", "test")
        finally:
            upload_module.uploadable_files = original_uploadable_files
            upload_module.upload_file = original_upload_file
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "authentication_failed")
        self.assertEqual(result["attempted"], 1)

    def test_upload_skips_identical_remote_file(self) -> None:
        import workflows.upload_and_trigger_cloud as upload_module

        original_get_existing_file = upload_module.get_existing_file
        original_github_contents_request = upload_module.github_contents_request
        content = (RELEASE_ROOT / "README.md").read_bytes()
        upload_module.get_existing_file = lambda repository, token, relative, branch: {
            "sha": upload_module.git_blob_sha(content)
        }

        def fail_if_put(*args, **kwargs):
            raise AssertionError("Identical files should not be uploaded.")

        upload_module.github_contents_request = fail_if_put
        try:
            result = upload_module.upload_file("owner/repo", "token", RELEASE_ROOT / "README.md", "main", "test")
        finally:
            upload_module.get_existing_file = original_get_existing_file
            upload_module.github_contents_request = original_github_contents_request
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "skipped")

    def test_create_upload_and_trigger_requires_owner_repo(self) -> None:
        result = create_upload_and_trigger("repo-without-owner", "token")
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "configuration")

    def test_cloud_connection_check_reports_missing_config(self) -> None:
        result = build_connection_check(None, None)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "configuration")
        self.assertIn("GITHUB_TOKEN or GH_TOKEN", result["missing"])
        self.assertIn("check-cloud-config-from-root.cmd", "\n".join(result["root_commands"]))
        self.assertIn("do not save", result["token_storage"])

    def test_cloud_connection_check_requires_owner_repo(self) -> None:
        result = build_connection_check("repo-without-owner", "token")
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "configuration")

    def test_cloud_connection_check_uses_local_repository_config(self) -> None:
        original_configured_repository = connection_module.configured_repository
        original_repository_env = os.environ.get("GITHUB_REPOSITORY")
        connection_module.configured_repository = lambda default=None: default or "owner/from-local-config"
        try:
            os.environ.pop("GITHUB_REPOSITORY", None)
            args = connection_module.parse_args([])
        finally:
            connection_module.configured_repository = original_configured_repository
            if original_repository_env is None:
                os.environ.pop("GITHUB_REPOSITORY", None)
            else:
                os.environ["GITHUB_REPOSITORY"] = original_repository_env
        self.assertEqual(args.repository, "owner/from-local-config")

    def test_cloud_run_reports_missing_config(self) -> None:
        result = build_cloud_run(None, None)
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "configuration")
        self.assertIn("run-cloud-test.cmd", result["next_command"])
        self.assertIn("setup-cloud-test.ps1", result["interactive_command"])
        self.assertIn("cloud_run.py", result["python_command"])

    def test_cloud_run_triggers_when_connection_ready(self) -> None:
        import workflows.cloud_run as cloud_run_module

        original_connection = cloud_run_module.build_connection_check
        original_trigger = cloud_run_module.trigger_cloud_acceptance
        cloud_run_module.build_connection_check = lambda repository, token, token_source_name="unknown": {"ok": True, "stage": "ready"}
        cloud_run_module.trigger_cloud_acceptance = lambda repository, token, ref: {
            "ok": True,
            "stage": "completed",
            "repository": repository,
            "ref": ref,
        }
        try:
            result = build_cloud_run("octocat/international-trade-ai", "token", branch="main")
        finally:
            cloud_run_module.build_connection_check = original_connection
            cloud_run_module.trigger_cloud_acceptance = original_trigger
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["stage"], "accepted")

    def test_cloud_test_status_reports_missing_configuration(self) -> None:
        status = build_cloud_test_status()
        self.assertIn("local_ready", status)
        self.assertIn("completion_evidence_required", status)
        self.assertIn("github-token-setup.md", status["token_setup_doc"])
        report = render_cloud_test_status(status)
        self.assertIn("Cloud Test Status", report)
        self.assertIn("run-cloud-test.cmd", report)
        self.assertIn("github-token-setup.md", report)

    def test_ensure_repository_can_report_missing_without_create(self) -> None:
        import workflows.create_repo_upload_and_trigger as create_module

        original_exists = create_module.repository_exists
        create_module.repository_exists = lambda repository, token: {"exists": False, "status": 404, "data": {}}
        try:
            result = ensure_repository("owner/repo", "token", create_if_missing=False)
        finally:
            create_module.repository_exists = original_exists
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "missing")

    def test_publish_summary_skips_without_github_env(self) -> None:
        original_summary_env = os.environ.get("GITHUB_STEP_SUMMARY")
        try:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
            result = publish_summary()
        finally:
            if original_summary_env is None:
                os.environ.pop("GITHUB_STEP_SUMMARY", None)
            else:
                os.environ["GITHUB_STEP_SUMMARY"] = original_summary_env
        self.assertFalse(result["published"])

    def test_watchdog_runs_against_current_state(self) -> None:
        status = run_watchdog()
        self.assertIn("waiting_for_owner", status)
        self.assertIn("age_hours", status)

    def test_watchdog_status_has_ok_field(self) -> None:
        status = build_watchdog_status(max_age_hours=0)
        self.assertIn("ok", status)

    def test_cloud_acceptance_status_covers_command_model(self) -> None:
        status = build_acceptance_status()
        self.assertIn("command_model", status)
        self.assertIn("checks", status)
        self.assertTrue(any(check["name"] == "codex_autonomy:autonomous_cases_recorded" for check in status["checks"]))
        self.assertTrue(any(check["name"] == "v11_knowledge:domains_and_customs" for check in status["checks"]))
        self.assertTrue(any(check["name"] == "v11_benchmark:50_questions" for check in status["checks"]))
        self.assertTrue(any(check["name"] == "v11_answer_scorer:daily_quality_score" for check in status["checks"]))
        self.assertTrue(any(check["name"] == "v11_evidence:verification_dossiers" for check in status["checks"]))
        self.assertTrue(any(check["name"] == "v11_action_board:execution_tasks" for check in status["checks"]))
        self.assertTrue(any(check["name"] == "v11_team_response:team_answer_pack" for check in status["checks"]))
        self.assertTrue(any(check["name"] == "v11_team_execution:packages_generated" for check in status["checks"]))
        self.assertTrue(any(check["name"] == "v11_search:source_readiness_and_confirmation_gate" for check in status["checks"]))
        self.assertTrue(any(check["name"] == "v11_project:promotion_readiness_gate" for check in status["checks"]))
        self.assertTrue(any(check["name"] == "v11_war_room:vertical_team_operating_package" for check in status["checks"]))
        self.assertTrue(any(check["name"] == "v11_mission_control:operating_brief" for check in status["checks"]))
        self.assertEqual(status["summary"]["search_confirmation_gate"], "lead_only")
        self.assertEqual(status["summary"]["promotion_gate_weak_lead"], "lead_only")
        self.assertEqual(status["summary"]["promotion_gate_official_project"], "draft_promotion_ready")
        self.assertGreaterEqual(status["summary"]["war_room_score"], 70)
        self.assertGreaterEqual(status["summary"]["war_room_roles"], 6)
        self.assertGreaterEqual(status["summary"]["war_rooms"], 1)
        self.assertEqual(status["summary"]["latest_war_room_mode"], "industry_war_room")

    def test_cloud_acceptance_report_names_goal(self) -> None:
        report = render_acceptance_report(
            {
                "ok": True,
                "created_at": "2026-06-21T00:00:00+00:00",
                "repository": "local",
                "run_id": "local",
                "summary": {"projects": 1},
                "checks": [{"name": "demo", "ok": True, "evidence": "ok"}],
            }
        )
        self.assertIn("GitHub Cloud Acceptance", report)
        self.assertIn("Codex = 24h autonomous executive", report)

    def test_cloud_acceptance_runs_against_current_state(self) -> None:
        original_summary_env = os.environ.get("GITHUB_STEP_SUMMARY")
        try:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
            status = run_acceptance()
        finally:
            if original_summary_env is None:
                os.environ.pop("GITHUB_STEP_SUMMARY", None)
            else:
                os.environ["GITHUB_STEP_SUMMARY"] = original_summary_env
        self.assertIn("report_path", status)
        self.assertIn("json_path", status)

    def test_decision_receipt_mentions_paths(self) -> None:
        receipt = build_decision_receipt(
            {
                "decision": "approve",
                "continuation_path": "memory/continuations/demo.md",
                "decision_path": "memory/decisions/demo.json",
            }
        )
        self.assertIn("Owner decision recorded: `approve`", receipt)
        self.assertIn("memory/continuations/demo.md", receipt)
        self.assertIn("memory/decisions/demo.json", receipt)

    def test_close_issue_skips_without_github_env(self) -> None:
        result = maybe_close_issue(123)
        self.assertFalse(result["closed"])


if __name__ == "__main__":
    unittest.main()
