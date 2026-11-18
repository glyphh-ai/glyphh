"""A short-lived, tamper-proof value in a URL: JSON, then an HMAC of it with the server's secret key.
Used to carry a sign-in through its steps without storing it."""

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from glyphh_server.errors import Invalid


def sign(secret: str, payload: dict[str, Any], ttl_seconds: int) -> str:
    body = json.dumps({**payload, "exp": int(time.time()) + ttl_seconds}, separators=(",", ":"))
    raw = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
    return f"{raw}.{_mac(secret, raw)}"


def verify(secret: str, token: str) -> dict[str, Any]:
    raw, _, mac = token.rpartition(".")
    if not raw or not hmac.compare_digest(mac, _mac(secret, raw)):
        raise Invalid("This sign-in link is not valid. Start again.", reason="invalid")
    body: dict[str, Any] = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    if body["exp"] < time.time():
        raise Invalid("This sign-in link has expired. Start again.", reason="expired")
    return body


def _mac(secret: str, raw: str) -> str:
    return hmac.new(secret.encode(), raw.encode(), hashlib.sha256).hexdigest()
