from __future__ import annotations

import os
from typing import Any


CORE_ENDPOINTS = (
    "/v1/query",
    "/v1/search",
    "/v1/projects",
    "/v1/cloud",
    "/v1/approvals",
)


def license_status() -> dict[str, Any]:
    require_license = os.getenv("CLOUD_OS_REQUIRE_LICENSE") == "1"
    endpoint = os.getenv("CLOUD_OS_LICENSE_ENDPOINT")
    enterprise_id = os.getenv("CLOUD_OS_ENTERPRISE_ID")
    token = os.getenv("CLOUD_OS_LICENSE_TOKEN")

    if not require_license:
        return {
            "status": "owner_mode",
            "allowed": True,
            "strict": False,
            "reason": "license not required for local owner mode",
        }

    if endpoint and enterprise_id and token:
        return {
            "status": "active",
            "allowed": True,
            "strict": True,
            "endpoint_configured": True,
            "enterprise_id": enterprise_id,
        }

    return {
        "status": "unconfigured",
        "allowed": False,
        "strict": True,
        "reason": "strict license mode requires endpoint, enterprise id, and runtime token",
    }


def core_allowed() -> bool:
    return bool(license_status().get("allowed"))
