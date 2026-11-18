"""Glyphh's products were retired on 2026-11-18: whatever still calls one of their addresses is told so, the same way
for all of them, 410 E_WOUND_DOWN in the API's own error shape; a runtime's link is closed 4401. The health check,
Stripe's webhook and the staff's way in go on."""

import logging
import uuid
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from httpx_ws import WebSocketDisconnect, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.api.gone import RETIRED, platform_only, staff_only
from glyphh_server.app import create_app
from glyphh_server.errors import WoundDown
from tests.api.browser import Staff
from tests.conftest import PLATFORM_ID, SETTINGS
from tests.fakes import fake_http

SAID: str = "Glyphh's products were retired on 2026-11-18. Questions: support@glyphh.ai"


def _gone(res: httpx.Response) -> None:
    assert res.status_code == 410, res.text
    assert res.headers["content-type"] == "application/json"
    assert res.json() == {"error": {"code": "E_WOUND_DOWN", "message": SAID, "trace_id": res.headers["x-request-id"]}}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/"),
        ("GET", "/docs"),
        ("GET", "/redoc"),
        ("GET", "/openapi.json"),
        ("POST", "/mcp"),
        ("GET", "/mcp"),
        ("DELETE", "/mcp"),
        ("POST", "/oauth/register"),
        ("GET", "/.well-known/oauth-authorization-server"),
        ("GET", "/.well-known/oauth-protected-resource/mcp"),
        ("POST", "/v1/device/code"),
        ("POST", "/v1/device/token"),
        ("GET", "/v1/device"),
        ("GET", "/v1/org"),
        ("POST", "/v1/invites/accept"),
        ("GET", "/v1/plans"),
        ("GET", "/v1/mods"),
        ("GET", "/v1/billing"),
        ("POST", "/v1/billing/checkout"),
        ("POST", "/v1/billing/portal"),
        ("POST", "/v1/billing/topup"),
        ("GET", "/billing/done"),
        ("GET", "/v1/license"),
        ("POST", "/v1/license/verify"),
        ("GET", "/v1/license/keys"),
        ("POST", "/v1/runtime/introspect"),
        ("POST", "/v1/runtime/local"),
        ("GET", "/v1/runtimes"),
        ("GET", "/v1/apps"),
        ("GET", "/v1/installs"),
        ("DELETE", "/v1/installs/0f0f0f0f-0000-4000-8000-000000000001"),
        ("POST", "/v1/sign-out"),
        ("POST", "/v1/me/source"),
        ("GET", "/v1/templates"),
        ("GET", "/v1/keys"),
        ("POST", "/v1/decide"),
        ("POST", "/v1/models"),
        ("POST", "/v1/chat/completions"),
        ("GET", "/auth/approve"),
        ("GET", "/auth/sso/start/again"),
        ("GET", "/auth"),
        ("GET", "/v1/admin"),
        ("GET", "/v1/health/now"),
        ("OPTIONS", "/v1/org"),
        ("OPTIONS", "/mcp"),
        ("PUT", "/anything/at/all"),
    ],
)
async def test_every_address_of_a_retired_product_is_gone(client: httpx.AsyncClient, method: str, path: str) -> None:
    for headers in ({}, {"host": "ada.glyphh.ai", "authorization": "Bearer a-token-from-before"}):
        _gone(await client.request(method, path, headers=headers, json={} if method == "POST" else None))


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/v1/health"),
        ("GET", "/v1/stripe/webhook"),
        ("DELETE", "/v1/me"),
        ("PATCH", "/v1/me"),
        ("OPTIONS", "/v1/me"),
        ("GET", "/oauth/token"),
        ("POST", "/oauth/authorize"),
        ("POST", "/auth/providers"),
        ("POST", "/auth/google/start"),
        ("DELETE", "/v1/admin/orgs"),
    ],
)
async def test_a_kept_address_asked_another_way_is_gone_too(client: httpx.AsyncClient, method: str, path: str) -> None:
    res = await client.request(method, path)
    _gone(res)
    assert "allow" not in res.headers


async def test_the_answer_keeps_the_callers_trace_and_is_logged_as_a_refusal(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="glyphh.api"):
        for method, path in (("GET", "/v1/org"), ("POST", "/v1/health")):
            res = await client.request(method, path, headers={"x-request-id": "an-old-plugin-0001"})
            _gone(res)
            assert res.headers["x-request-id"] == "an-old-plugin-0001"
    refused: list[Any] = [r.fields for r in caplog.records if r.getMessage() == "refused"]  # type: ignore[attr-defined]
    assert refused == [{"code": "E_WOUND_DOWN", "status": 410}] * 2


async def test_a_runtimes_link_is_closed_with_the_code_rrotor_stops_on(engine: AsyncEngine) -> None:
    app = create_app(SETTINGS, http=fake_http())
    http = httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test")
    async with LifespanManager(app), http:
        for path in ("/v1/runtime/link", "/mcp", "/v1/health", "/anything/at/all"):
            async with aconnect_ws(f"http://test{path}", http) as ws:
                with pytest.raises(WebSocketDisconnect) as closed:
                    await ws.receive(timeout=5)
            assert (closed.value.code, closed.value.reason) == (4401, SAID), path


async def test_the_health_check_stripes_webhook_and_the_staffs_way_in_go_on(
    client: httpx.AsyncClient, staff: Staff
) -> None:
    health = await client.get("/v1/health")
    assert health.json() == {"status": "ok", "version": "test", "database": True, "redis": True}
    unsigned = await client.post("/v1/stripe/webhook", content=b"{}", headers={"stripe-signature": "t=1,v1=x"})
    assert (unsigned.status_code, unsigned.json()["error"]["code"]) == (401, "E_UNAUTHORIZED")
    assert "signed by Stripe" in unsigned.json()["error"]["message"]
    me = await staff.http.get("/v1/me", headers=staff.who.headers)
    assert me.status_code == 200 and (me.json()["email"], me.json()["staff"]) == (staff.who.email, True)
    assert (await client.get("/v1/me")).status_code == 401
    assert (await client.get("/auth/providers")).json() == {"providers": ["google", "github"], "sso": False}
    assert (await client.get("/oauth/authorize")).status_code == 422
    assert (await client.post("/oauth/token")).json()["error"] == "invalid_client"
    assert (await client.post("/oauth/revoke")).status_code == 401
    assert (await client.get("/v1/admin/orgs")).status_code == 401


def test_only_glyphhs_staff_and_the_platforms_own_client_are_let_in() -> None:
    assert RETIRED == SAID
    several = SETTINGS.model_copy(update={"staff_emails": " Support@Glyphh.ai ,, second@glyphh.test"})
    for settings, email in (
        (SETTINGS, "support@glyphh.ai"),
        (several, " SUPPORT@glyphh.ai "),
        (several, "second@glyphh.test"),
    ):
        staff_only(settings, email)
    for settings, email in ((SETTINGS, "second@glyphh.test"), (SETTINGS, ""), (several, "support@glyphh.test")):
        with pytest.raises(WoundDown, match="retired on 2026-11-18"):
            staff_only(settings, email)
    platform_only(SETTINGS, PLATFORM_ID)
    platform_only(SETTINGS.model_copy(update={"platform_client_id": f" {str(PLATFORM_ID).upper()} "}), PLATFORM_ID)
    for settings in (
        SETTINGS.model_copy(update={"platform_client_id": ""}),
        SETTINGS.model_copy(update={"platform_client_id": "x"}),
    ):
        with pytest.raises(WoundDown):
            platform_only(settings, PLATFORM_ID)
    with pytest.raises(WoundDown):
        platform_only(SETTINGS, uuid.uuid4())
