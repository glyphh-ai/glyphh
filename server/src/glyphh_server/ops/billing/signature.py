"""Stripe's webhook signature: Stripe-Signature carries t=<unix time> and v1=<hex HMAC-SHA256 of "t.body" with the
endpoint's secret>. A missing, wrong or old signature is refused."""

import hashlib
import hmac
import json
import time
from typing import Any

from glyphh_server.errors import Unauthorized, Unavailable

TOLERANCE: int = 300


def sign(secret: str, body: bytes, at: int) -> str:
    mac = hmac.new(secret.encode(), f"{at}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={at},v1={mac}"


def verified_event(secret: str, body: bytes, header: str | None, now: float | None = None) -> dict[str, Any]:
    if not secret:
        raise Unavailable("Billing isn't set up on this server.", reason="billing_off")
    parts = [p.split("=", 1) for p in (header or "").split(",") if "=" in p]
    stamps = [v for k, v in parts if k == "t"]
    macs = [v for k, v in parts if k == "v1"]
    if not stamps or not stamps[0].isdigit():
        raise Unauthorized("This webhook isn't signed by Stripe.")
    at = int(stamps[0])
    expected = sign(secret, body, at).split("v1=")[1]
    if not any(hmac.compare_digest(expected, m) for m in macs):
        raise Unauthorized("This webhook isn't signed by Stripe.")
    if abs((now or time.time()) - at) > TOLERANCE:
        raise Unauthorized("This webhook's signature is too old.")
    return json.loads(body)
