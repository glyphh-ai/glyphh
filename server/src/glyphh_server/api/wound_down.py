"""Glyphh's products, wound down (2026-11-18): with GLYPHH_PRODUCTS off, the default, this layer answers every request
410 E_WOUND_DOWN but the few that go on, and nothing below it runs for the rest. Nothing is deleted: turning the
switch on brings every route back as it was.

What goes on: the health check (Fly's, and CI's after a deploy); Stripe's webhook, so cancellations and final invoices
are still recorded on their orgs; `/mcp`, which answers every client truthfully with no tools (mcp/retired.py); and
the staff's own way in, the platform's sign-in for an account whose email is in GLYPHH_STAFF_EMAILS (`staff_only`,
below) and the staff view behind it. Nobody else signs in, and nobody signs up. A runtime's link is accepted and
closed 4401, the code rrotor stops reconnecting on."""

import logging
import re
import uuid

from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from glyphh_server.api.errors import error_body
from glyphh_server.config import Settings
from glyphh_server.errors import WoundDown
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.api")

RETIRED: str = "Glyphh's products were retired on 2026-11-18. Questions: support@glyphh.ai"
LINK_CLOSED: int = 4401
OPEN: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", "/v1/health"),
        ("POST", "/v1/stripe/webhook"),
        ("POST", "/mcp"),
        ("GET", "/mcp"),
        ("DELETE", "/mcp"),
        ("GET", "/v1/me"),
        ("GET", "/oauth/authorize"),
        ("POST", "/oauth/token"),
        ("POST", "/oauth/revoke"),
        ("GET", "/auth/providers"),
        ("GET", "/auth/consent"),
        ("GET", "/auth/oauth/allow"),
    }
)
# The staff view, and the two provider steps of its sign-in (single sign-on is an org's, so not among them).
OPEN_LIKE: re.Pattern[str] = re.compile(r"/v1/admin/.+|/auth/(google|github)/(start|callback)")


def is_open(method: str, path: str) -> bool:
    return (method, path) in OPEN or (method != "OPTIONS" and OPEN_LIKE.fullmatch(path) is not None)


def staff_only(settings: Settings, email: str) -> None:
    """Wound down, only Glyphh's staff sign in or call: anyone else is told the products are retired."""
    if not settings.products and email.strip().lower() not in settings.staff_set:
        raise WoundDown(RETIRED)


def platform_only(settings: Settings, client_id: uuid.UUID) -> None:
    """Wound down, only the platform's own OAuth client is issued tokens: a connector's is refused."""
    if not settings.products and str(client_id) != settings.platform_client_id.strip().lower():
        raise WoundDown(RETIRED)


class WoundDownMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await receive()  # its connect
            await send({"type": "websocket.accept"})
            await send({"type": "websocket.close", "code": LINK_CLOSED, "reason": RETIRED})
        elif scope["type"] != "http" or is_open(scope["method"], scope["path"]):
            await self.app(scope, receive, send)
        else:
            log.info("refused", extra=fields(code=WoundDown.code, status=WoundDown.status))
            await JSONResponse(error_body(WoundDown.code, RETIRED), WoundDown.status)(scope, receive, send)
