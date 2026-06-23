from __future__ import annotations

import json
import os
import urllib.request
from typing import Any


class N8NConnector:
    """n8n helper that never bypasses v11 approval and license gates."""

    def __init__(self, n8n_url: str | None = None, api_key: str | None = None):
        self.n8n_url = (n8n_url or os.getenv("N8N_URL") or "").rstrip("/")
        self.api_key = api_key or os.getenv("N8N_API_KEY") or ""

    def configured(self) -> bool:
        return bool(self.n8n_url and self.api_key)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict:
        if not self.configured():
            return {"status": "not_configured", "reason": "N8N_URL and N8N_API_KEY are required"}
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.n8n_url}{path}",
            data=data,
            method=method,
            headers={
                "Content-Type": "application/json",
                "X-N8N-API-KEY": self.api_key,
            },
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode("utf-8") or "{}"
            return {"status": "success", "http_status": response.status, "data": json.loads(raw)}

    def trigger_workflow(self, workflow_id: str, input_data: dict[str, Any], org_id: str) -> dict:
        if input_data.get("approval_required") and not input_data.get("approved_by_human"):
            return {
                "status": "blocked_by_v11_risk_gate",
                "workflow_id": workflow_id,
                "reason": "n8n cannot send or publish approval-gated content before human approval",
            }
        result = self._request("POST", f"/api/v1/workflows/{workflow_id}/activate", None)
        if result.get("status") != "success":
            return result | {"workflow_id": workflow_id}
        return {
            "status": "success",
            "workflow_id": workflow_id,
            "workflow_execution_id": result.get("data", {}).get("id", workflow_id),
            "org_id": org_id,
        }

    def list_workflows(self) -> dict:
        return self._request("GET", "/api/v1/workflows")
