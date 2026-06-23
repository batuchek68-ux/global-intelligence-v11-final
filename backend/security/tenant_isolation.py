from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

logger = logging.getLogger(__name__)


class TenantIsolationManager:
    """Minimal tenant isolation helper for the v11 architecture pass."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.secret_key = str(config.get("SECRET_KEY") or "change-me")
        self.token_expiry_seconds = int(config.get("TOKEN_EXPIRY_SECONDS", 3600))

    def generate_api_key(self, org_id: str, user_id: str) -> str:
        raw_key = f"{org_id}:{user_id}:{datetime.now(timezone.utc).timestamp()}"
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def verify_api_key(self, api_key: str, stored_hash: str) -> bool:
        provided_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        return hmac.compare_digest(provided_hash, stored_hash)

    def generate_token(self, org_id: str, user_id: str) -> str:
        payload = {
            "org_id": org_id,
            "user_id": user_id,
            "exp": (datetime.now(timezone.utc) + timedelta(seconds=self.token_expiry_seconds)).timestamp(),
        }
        encoded_payload = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")
        signature = hmac.new(self.secret_key.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{encoded_payload}.{signature}"

    def verify_token(self, token: str) -> dict[str, Any] | None:
        try:
            encoded_payload, signature = token.split(".", 1)
            expected = hmac.new(self.secret_key.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return None
            payload = json.loads(base64.urlsafe_b64decode(encoded_payload.encode("ascii")).decode("utf-8"))
            if float(payload.get("exp", 0)) < datetime.now(timezone.utc).timestamp():
                return None
            return payload
        except Exception:
            return None

    def enforce_tenant_filter(self, org_id: str, query_dict: dict[str, Any]) -> dict[str, Any]:
        query_dict["tenant_id"] = org_id
        return query_dict


def require_org_id(func):
    @wraps(func)
    async def decorated_function(request, *args, **kwargs):
        org_id = request.headers.get("X-Org-ID")
        if not org_id or not _is_valid_org_id(org_id):
            return {"error": "Missing or invalid X-Org-ID header"}, 401
        request.scope["org_id"] = org_id
        return await func(request, *args, **kwargs)

    return decorated_function


def _is_valid_org_id(org_id: str) -> bool:
    return 0 < len(org_id) < 256 and all(ch.isalnum() or ch in "-_" for ch in org_id)
