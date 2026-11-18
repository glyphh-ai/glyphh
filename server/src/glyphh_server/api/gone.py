"""Glyphh's products were retired on 2026-11-18 and their code is deleted. Whatever still calls one of their addresses
(an old plugin or SDK, a rrotor install, Claude's connector at `/mcp`) is answered here, the same way for all of
them: 410 E_WOUND_DOWN, in the API's own error shape, so a client can tell "gone" from "broken" and stop retrying.
A runtime's link (a WebSocket, on any path) is accepted and closed 4401, the code rrotor stops reconnecting on.

What is left is the app's own routes (app.py): the health check, Stripe's webhook, and the staff's way in, the
platform's sign-in for an account whose email is in GLYPHH_STAFF_EMAILS (`staff_only`) through the platform's own
OAuth client (`platform_only`), with `GET /v1/me` and the staff view behind it. Nobody else signs in, and nobody
signs up."""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from glyphh_server.api.errors import error_body
from glyphh_server.config import Settings
from glyphh_server.errors import WoundDown
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.api")

RETIRED: str = "Glyphh's products were retired on 2026-11-18. Questions: support@glyphh.ai"
LINK_CLOSED: int = 4401


def staff_only(settings: Settings, email: str) -> None:
    """Only Glyphh's staff sign in or call: anyone else is told the products are retired."""
    if email.strip().lower() not in settings.staff_set:
        raise WoundDown(RETIRED)


def platform_only(settings: Settings, client_id: uuid.UUID) -> None:
    """Only the platform's own OAuth client is issued tokens: any other left in the database is refused."""
    if str(client_id) != settings.platform_client_id.strip().lower():
        raise WoundDown(RETIRED)


def answer() -> JSONResponse:
    log.info("refused", extra=fields(code=WoundDown.code, status=WoundDown.status))
    return JSONResponse(error_body(WoundDown.code, RETIRED), WoundDown.status)


async def gone(scope: Scope, receive: Receive, send: Send) -> None:
    """What the router answers when no route is at the address."""
    if scope["type"] == "websocket":
        await receive()  # its connect
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.close", "code": LINK_CLOSED, "reason": RETIRED})
    else:
        await answer()(scope, receive, send)


async def _wrong_method(request: Request, err: Exception) -> JSONResponse:
    return answer()


def install(app: FastAPI) -> None:
    """Every address without a route, and a route asked with a method it does not take (the router's 405)."""
    app.router.default = gone
    app.add_exception_handler(405, _wrong_method)
