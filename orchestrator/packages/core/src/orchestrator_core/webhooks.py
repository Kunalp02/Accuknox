"""Webhook HMAC signing."""

import hashlib
import hmac
import json
from typing import Any


def sign_webhook_payload(secret: str, payload: dict[str, Any]) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    digest = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"sha256={digest}"
