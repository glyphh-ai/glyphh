"""GLYPHH_PRODUCTS, off by default (the products were retired on 2026-11-18): every product route answers 410
E_WOUND_DOWN on every host, /mcp tells a client the truth with no tools and no sign-in, a runtime's link is closed
4401, the tick tends no product, and Stripe's webhook and the health check go on. Only Glyphh's staff sign in, through
the platform's own client; nobody signs up. On, everything is as before (the rest of the suite)."""

import json
import time
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from redis.asyncio import Redis
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.api.wound_down import RETIRED, is_open
from glyphh_server.app import create_app
from glyphh_server.config import Settings
from glyphh_server.models import OAuthClient, Org, User
from glyphh_server.ops import tend
from glyphh_server.ops.billing.signature import sign
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.plans import org_version
from tests.api.browser import error_page, new_code
from tests.conftest import PROVIDER_SETTINGS, WEBHOOK_SECRET, _client
from tests.connector import REDIRECT, allow, ask, exchange, modern, modern_headers, query, to_allow
from tests.db.helpers import an_email, org_row, person, subscribed
from tests.fakes import GOOGLE_ME, FakeStripe, fake_http
from tests.link import closed

PLATFORM_ID: str = "0f0f0f0f-0000-4000-8000-0000000d0d0d"
GONE: dict[str, Any] = {"code": "E_WOUND_DOWN", "message": RETIRED}


def wound_down(**over: Any) -> Settings:
    """The suite's settings with the products off, validated again so the switch takes the others with it."""
    return Settings(**{**PROVIDER_SETTINGS.model_dump(), "products": False, "platform_client_id": PLATFORM_ID, **over})


OFF: Settings = wound_down()


@pytest.fixture
async def off(engine: AsyncEngine, stripe: FakeStripe) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(create_app(OFF, http=fake_http(stripe))):
        yield c


async def _browser(email: str, settings: Settings = OFF) -> AsyncIterator[httpx.AsyncClient]:
    """A browser whose Google account has this email."""
    over = {("GET", "/v1/userinfo"): {**GOOGLE_ME, "sub": f"g-{email}", "email": email}}
    async for c in _client(create_app(settings, http=fake_http(None, over))):
        yield c


async def _oauth_client(engine: AsyncEngine, client_id: str | None = None) -> dict[str, Any]:
    """A public OAuth client made in the database (registering one is refused): the platform's own under its id."""
    values = {"name": "Glyphh", "redirect_uris": [REDIRECT], "auth_method": "none"}
    values |= {"grant_types": ["authorization_code", "refresh_token"], "id": uuid.UUID(client_id or str(uuid.uuid4()))}
    async with engine.begin() as conn:
        await conn.execute(insert(OAuthClient).values(values))
    return {"client_id": str(values["id"]), "redirect_uris": [REDIRECT]}


def test_the_products_are_off_by_default_and_take_their_own_switches_with_them(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GLYPHH_PRODUCTS")
    assert Settings(_env_file=None).products is False  # type: ignore[call-arg]
    off = Settings(ada_cloud=True, llm=True, rrotor=True)
    assert (off.ada_cloud, off.llm, off.rrotor, off.hosted) == (False, False, False, False)
    on = Settings(products=True, ada_cloud=True, llm=True)
    assert (on.ada_cloud, on.rrotor, on.hosted) == (True, True, True)


def test_only_the_health_check_the_webhook_mcp_and_the_staffs_way_in_stay_open() -> None:
    for method, path in (("GET", "/v1/health"), ("POST", "/v1/stripe/webhook"), ("POST", "/mcp"), ("GET", "/v1/me")):
        assert is_open(method, path)
    assert is_open("GET", "/v1/admin/orgs") and is_open("POST", "/v1/admin/events/ack")
    assert is_open("GET", "/auth/google/start") and is_open("GET", "/auth/github/callback")
    for path in ("/auth/sso/start", "/auth/approve", "/v1/admin/", "/v1/plans"):
        assert not is_open("GET", path)
    assert not is_open("PATCH", "/v1/me") and not is_open("OPTIONS", "/v1/admin/orgs")


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/v1/plans"),
        ("GET", "/v1/mods"),
        ("POST", "/v1/device/code"),
        ("POST", "/v1/device/token"),
        ("GET", "/v1/license"),
        ("POST", "/v1/license/verify"),
        ("POST", "/v1/runtime/introspect"),
        ("GET", "/v1/billing"),
        ("POST", "/v1/billing/checkout"),
        ("POST", "/v1/billing/portal"),
        ("GET", "/v1/templates"),
        ("POST", "/v1/me/glyphh/context"),
        ("GET", "/v1/org"),
        ("POST", "/v1/invites/accept"),
        ("GET", "/v1/keys"),
        ("POST", "/v1/decide"),
        ("POST", "/v1/chat/completions"),
        ("POST", "/oauth/register"),
        ("GET", "/.well-known/oauth-authorization-server"),
        ("GET", "/.well-known/oauth-protected-resource/mcp"),
        ("GET", "/auth/sso/start"),
        ("GET", "/auth/approve"),
        ("GET", "/openapi.json"),
        ("GET", "/"),
    ],
)
async def test_every_product_route_is_gone_on_every_host(off: httpx.AsyncClient, method: str, path: str) -> None:
    for host in ("api.glyphh.ai", "ada.glyphh.ai"):
        res = await off.request(method, path, headers={"host": host})
        assert res.status_code == 410, res.text
        assert res.json() == {"error": {**GONE, "trace_id": res.headers["x-request-id"]}}


async def test_ada_cloud_asked_on_stays_off_and_its_host_is_gone(engine: AsyncEngine) -> None:
    app = create_app(wound_down(ada_cloud=True), http=fake_http())
    assert app.state.ada is None
    async for c in _client(app):
        res = await c.post("/v1/models", headers={"host": "ada.glyphh.ai", "authorization": "Bearer glyphh_ak_x"})
        assert (res.status_code, res.json()["error"]["code"]) == (410, "E_WOUND_DOWN")


async def test_the_health_check_goes_on(off: httpx.AsyncClient) -> None:
    res = await off.get("/v1/health")
    assert res.json() == {"status": "ok", "version": "test", "database": True, "redis": True}


async def test_stripes_webhook_still_records_a_cancellation(
    off: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Team")
    sub, customer = f"sub_{uuid.uuid4().hex}", f"cus_{uuid.uuid4().hex}"
    await subscribed(engine, ada.org_id, sub, customer)
    stripe.sub(sub, customer, "price_test_team", 1, "canceled")
    event = {"id": "evt_1", "type": "customer.subscription.deleted"}
    event["data"] = {"object": {"id": sub, "customer": customer, "metadata": {}, "status": "canceled"}}
    body = json.dumps(event).encode()
    headers = {"stripe-signature": sign(WEBHOOK_SECRET, body, int(time.time())), "content-type": "application/json"}
    assert (await off.post("/v1/stripe/webhook", content=body, headers=headers)).status_code == 204
    org = await org_row(engine, ada.org_id)
    assert (org.billing_status, org.stripe_subscription_id) == ("canceled", None)
    async with engine.connect() as conn:
        assert (await org_version(conn, ada.org_id)).name == "Free"
    unsigned = await off.post("/v1/stripe/webhook", content=body, headers={"stripe-signature": "t=1,v1=x"})
    assert unsigned.status_code == 401


async def _legacy(http: httpx.AsyncClient, method: str, **params: Any) -> httpx.Response:
    return await http.post("/mcp", json={"jsonrpc": "2.0", "id": 7, "method": method, "params": params})


async def test_mcp_tells_an_earlier_client_the_truth_with_no_sign_in(off: httpx.AsyncClient) -> None:
    hello = (await _legacy(off, "initialize", protocolVersion="2025-06-18")).json()["result"]
    assert hello["protocolVersion"] == "2025-06-18" and hello["instructions"] == RETIRED
    assert hello["capabilities"] == {"tools": {}, "resources": {}} and hello["serverInfo"]["name"] == "glyphh"
    assert (await _legacy(off, "initialize", protocolVersion="1999-01-01")).json()["result"]["protocolVersion"] == (
        "2025-11-25"
    )
    assert (await _legacy(off, "ping")).json() == {"jsonrpc": "2.0", "id": 7, "result": {}}
    assert (await _legacy(off, "tools/list")).json()["result"] == {"tools": []}
    assert (await _legacy(off, "resources/list")).json()["result"] == {"resources": []}
    assert (await _legacy(off, "resources/templates/list")).json()["result"] == {"resourceTemplates": []}
    for method, params in (("tools/call", {"name": "whoami", "arguments": {}}), ("resources/read", {"uri": "ui://x"})):
        called = await _legacy(off, method, **params)
        assert called.status_code == 200
        gone = {"code": -32010, "message": RETIRED, "data": {"code": "E_WOUND_DOWN", "method": method}}
        assert called.json() == {"jsonrpc": "2.0", "id": 7, "error": gone}
    note = await off.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert note.status_code == 202


async def test_mcp_tells_a_modern_client_the_truth_too(off: httpx.AsyncClient) -> None:
    stale = {"authorization": "Bearer a-token-from-before"}  # never read: no 401, so no sign-in loop

    async def ask_mcp(method: str, **params: Any) -> dict[str, Any]:
        body = modern(method, params)
        res = await off.post("/mcp", json=body, headers=modern_headers(body, stale))
        assert res.status_code == 200, res.text
        return res.json()

    found = (await ask_mcp("server/discover"))["result"]
    assert found["instructions"] == RETIRED and found["supportedVersions"][0] == "2026-07-28"
    listed = (await ask_mcp("tools/list"))["result"]
    assert (listed["tools"], listed["ttlMs"], listed["cacheScope"]) == ([], 0, "private")
    for method, params in (("tools/call", {"name": "ada_decide", "arguments": {}}), ("initialize", {})):
        error = (await ask_mcp(method, **params))["error"]
        assert (error["code"], error["message"], error["data"]["code"]) == (-32010, RETIRED, "E_WOUND_DOWN")


async def test_mcp_still_refuses_what_it_always_refused(off: httpx.AsyncClient) -> None:
    assert (await off.post("/mcp", content=b"not json")).json()["error"]["code"] == -32700
    assert (await off.get("/mcp")).status_code == 405
    ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    assert (await off.post("/mcp", json=ping, headers={"origin": "https://x"})).status_code == 403


async def test_a_runtimes_link_is_closed_with_the_code_rrotor_stops_on(engine: AsyncEngine) -> None:
    app = create_app(OFF, http=fake_http())
    http = httpx.AsyncClient(transport=ASGIWebSocketTransport(app=app), base_url="http://test")
    async with LifespanManager(app), http, aconnect_ws("http://test/v1/runtime/link", http) as ws:
        assert await closed(ws) == (4401, RETIRED)


async def test_the_tick_tends_nothing_of_a_products(engine: AsyncEngine, redis: Redis) -> None:
    who = await person(engine, "Enterprise")
    async with engine.begin() as conn:
        lapsed = {"plan_until": datetime.now(UTC) - timedelta(minutes=1)}
        await conn.execute(update(Org).where(Org.id == who.org_id).values(**lapsed))
    never: Any = object()  # GitHub's traffic client: used, the tick would fail
    assert await tend.tend(engine, Hub(redis), OFF, 60, None, None, never)
    async with engine.connect() as conn:
        assert (await org_version(conn, who.org_id)).name == "Enterprise"


async def _users(engine: AsyncEngine, email: str) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(select(func.count()).where(func.lower(User.email) == email))).scalar_one()


async def test_staff_sign_in_through_the_platform_and_reach_the_staff_view(engine: AsyncEngine) -> None:
    email = f"staff-{uuid.uuid4().hex[:10]}@glyphh.test"
    platform = await _oauth_client(engine, PLATFORM_ID)
    connector = await _oauth_client(engine)
    await person(engine, email=email)
    async for http in _browser(email, wound_down(staff_emails=email)):
        _, consent = await to_allow(http, ask(platform))
        tokens = await exchange(http, platform, query(await allow(http, consent, "allow"))["code"])
        assert tokens.status_code == 200, tokens.text
        auth = {"authorization": f"Bearer {tokens.json()['access_token']}"}
        me = await http.get("/v1/me", headers=auth)
        assert (me.status_code, me.json()["staff"], me.json()["ada_cloud"]) == (200, True, False)
        assert (await http.get("/v1/admin/orgs", headers=auth)).status_code == 200
        assert (await http.get("/v1/org", headers=auth)).status_code == 410
        # A connector's client, even for staff, is issued nothing.
        _, consent = await to_allow(http, ask(connector))
        refused = await exchange(http, connector, query(await allow(http, consent, "allow"))["code"])
        assert (refused.status_code, refused.json()["error"]["code"]) == (410, "E_WOUND_DOWN")


async def test_nobody_else_signs_in_and_nobody_signs_up(engine: AsyncEngine) -> None:
    platform = await _oauth_client(engine)
    known, new = await person(engine), an_email()
    for email in (known.email, new):
        async for http in _browser(email):
            path = (await http.get("/oauth/authorize", params=ask(platform))).headers["location"]
            oauth = dict(httpx.URL(path).params)["oauth"]
            started = await http.get("/auth/google/start", params={"oauth": oauth})
            state = dict(httpx.URL(started.headers["location"]).params)["state"]
            back = await http.get("/auth/google/callback", params={"code": "c-1", "state": state})
            assert error_page(back)["code"] == "E_WOUND_DOWN"
            assert error_page(back)["message"] == RETIRED
    assert await _users(engine, new) == 0


async def test_a_token_from_before_is_no_good_unless_it_is_staffs(off: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    res = await off.get("/v1/me", headers=ada.headers)
    assert (res.status_code, res.json()["error"]["code"]) == (410, "E_WOUND_DOWN")
    assert (await off.get("/v1/me")).status_code == 401
    staff = await person(engine, email=f"staff-{uuid.uuid4().hex[:10]}@glyphh.test")
    async for http in _client(create_app(wound_down(staff_emails=staff.email), http=fake_http())):
        assert (await http.get("/v1/me", headers=staff.headers)).status_code == 200


async def test_a_device_sign_in_begun_before_the_switch_ends_at_the_provider(engine: AsyncEngine) -> None:
    email = an_email()
    async for before in _browser(email, PROVIDER_SETTINGS):
        code = await new_code(before)
        started = await before.get("/auth/google/start", params={"code": code["user_code"]})
        state = dict(httpx.URL(started.headers["location"]).params)["state"]
        async for after in _browser(email):
            after.cookies.update(before.cookies)
            back = await after.get("/auth/google/callback", params={"code": "c-1", "state": state})
            assert error_page(back)["code"] == "E_WOUND_DOWN"
    assert await _users(engine, email) == 0
