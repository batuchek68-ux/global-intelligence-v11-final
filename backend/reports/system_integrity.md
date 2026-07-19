# v11 System Integrity Report

- Status: PASS
- Generated: 2026-07-19T04:06:36.677968+00:00
- Auto fix: True

## Repairs

- No low-risk repair needed.

## Checks

- PASS dir:backend/memory
- PASS dir:backend/reports
- PASS dir:backend/comm/outbox
- PASS dir:backend/workflows
- PASS dir:backend/services
- PASS dir:backend/integrations
- PASS dir:apps/decision-hub/public
- PASS dir:apps/desktop-cloud-os/src
- PASS dir:.github/workflows
- PASS file:AGENTS.md
- PASS file:README.md
- PASS file:.github/workflows/cloud_acceptance.yml
- PASS file:.github/workflows/watchdog.yml
- PASS file:.github/workflows/codex_autonomous_repair.yml
- PASS file:backend/services/audit_service.py
- PASS file:backend/services/evidence_verification_service.py
- PASS file:backend/services/industry_war_room_service.py
- PASS file:backend/services/intelligence_center_service.py
- PASS file:backend/services/knowledge_benchmark_service.py
- PASS file:backend/services/mission_control_service.py
- PASS file:backend/services/project_action_board_service.py
- PASS file:backend/services/project_intelligence_service.py
- PASS file:backend/services/self_improvement_service.py
- PASS file:backend/services/social_communication_service.py
- PASS file:backend/services/team_execution_service.py
- PASS file:backend/services/team_response_service.py
- PASS file:backend/services/war_room_execution_queue_service.py
- PASS file:backend/comm/chat_gateway.py
- PASS file:backend/integrations/n8n_connector.py
- PASS file:apps/desktop-cloud-os/scripts/prepare-resources.js
- PASS secret_scan:no_plaintext_tokens
- PASS actions:uses_backend_workflows
- PASS n8n:approval_gate_documented
- PASS audit:append_service_available
- PASS evidence_verification:dossier_service_available
- PASS industry_war_room:vertical_team_package_available
- PASS intelligence_center:service_available
- PASS knowledge_benchmark:service_available
- PASS mission_control:operating_brief_available
- PASS project_action_board:execution_board_available
- PASS project_intelligence:library_service_available
- PASS self_improvement:service_available
- PASS social_communication:approval_gate_available
- PASS team_execution:project_team_os_available
- PASS team_response:team_answer_pack_available
- PASS war_room_execution:queue_service_available
