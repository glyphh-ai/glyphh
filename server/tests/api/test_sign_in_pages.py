"""A member signs in for an agent host through the pages, the way a browser does it."""

import re
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import OAuthClient
from tests.conftest import _client
from tests.fake_providers import PROVIDER_SETTINGS, provider_transport
from tests.mcp.test_oauth_flow import REDIRECT, _pkce, _register


@pytest.fixture
async def browser(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(PROVIDER_SETTINGS, http=httpx.AsyncClient(transport=provider_transport()))

    async def crash() -> None:
        raise RuntimeError("page internals")

    app.add_api_route("/auth/probe-crash", crash, methods=["GET"])
    async for c in _client(app):
        yield c


def _path(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.path}?{parts.query}"


async def _to_allow(browser: httpx.AsyncClient, provider: str = "google") -> tuple[str, dict]:
    host = await _register(browser, token_endpoint_auth_method="none", client_name="Claude")
    verifier, challenge = _pkce()
    link = (
        await browser.get(
            "/authorize",
            params={
                "response_type": "code",
                "client_id": host["client_id"],
                "redirect_uri": REDIRECT,
                "state": "st-9",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
    ).headers["location"]
    page = await browser.get(_path(link))
    assert page.status_code == 200 and "Continue with Google" in page.text and "Continue with GitHub" in page.text
    assert page.headers["x-frame-options"] == "DENY" and "glyphh_signin" in page.headers["set-cookie"]
    started = await browser.get(_path(link).replace("/auth/sign-in", f"/auth/{provider}/start"))
    assert started.status_code == 302
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    allow = await browser.get(f"/auth/{provider}/callback", params={"code": "c-1", "state": state})
    assert allow.status_code == 200, allow.text
    return allow.text, {"host": host, "verifier": verifier, "state": state}


def _consent(html: str) -> str:
    return re.search(r"name=consent value='([^']+)'", html).group(1)  # type: ignore[union-attr]


async def test_signing_in_with_google_and_allowing_gives_the_host_a_code(browser: httpx.AsyncClient) -> None:
    html, ctx = await _to_allow(browser)
    assert "Claude wants to use your Glyphh" in html and "pages@google.test" in html
    back = await browser.post("/auth/allow", data={"consent": _consent(html), "decision": "allow"})
    assert back.status_code == 303 and back.headers["location"].startswith(REDIRECT)
    query = parse_qs(urlsplit(back.headers["location"]).query)
    assert query["state"] == ["st-9"]
    issued = await browser.post(
        "/token",
        data={
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": REDIRECT,
            "client_id": ctx["host"]["client_id"],
            "code_verifier": ctx["verifier"],
        },
    )
    assert issued.status_code == 200
    me = await browser.get("/v1/me", headers={"authorization": f"Bearer {issued.json()['access_token']}"})
    assert me.json()["email"] == "pages@google.test"


async def test_github_works_the_same_and_deny_tells_the_host_no(browser: httpx.AsyncClient) -> None:
    html, _ = await _to_allow(browser, "github")
    assert "octo@gh.test" in html
    back = await browser.post("/auth/allow", data={"consent": _consent(html), "decision": "deny"})
    query = parse_qs(urlsplit(back.headers["location"]).query)
    assert back.status_code == 303 and query["error"] == ["access_denied"] and query["state"] == ["st-9"]


async def test_a_sign_in_from_another_browser_is_refused(browser: httpx.AsyncClient, engine: AsyncEngine) -> None:
    html, ctx = await _to_allow(browser)
    async for stranger in _client(
        create_app(PROVIDER_SETTINGS, http=httpx.AsyncClient(transport=provider_transport()))
    ):
        for res in (
            await stranger.post("/auth/allow", data={"consent": _consent(html), "decision": "allow"}),
            await stranger.get("/auth/google/callback", params={"code": "c", "state": ctx["state"]}),
        ):
            assert res.status_code == 422 and "E_INVALID" in res.text and "Start again" in res.text
            assert "text/html" in res.headers["content-type"]


async def test_a_cancelled_or_crossed_provider_sign_in_is_refused(browser: httpx.AsyncClient) -> None:
    _, ctx = await _to_allow(browser)
    cancelled = await browser.get("/auth/google/callback", params={"state": ctx["state"], "error": "access_denied"})
    assert cancelled.status_code == 403 and "cancelled" in cancelled.text
    crossed = await browser.get("/auth/github/callback", params={"code": "c", "state": ctx["state"]})
    assert crossed.status_code == 422


async def test_a_host_removed_mid_sign_in_is_refused(browser: httpx.AsyncClient, engine: AsyncEngine) -> None:
    _, ctx = await _to_allow(browser)
    async with engine.begin() as conn:
        await conn.execute(delete(OAuthClient).where(OAuthClient.client_id == ctx["host"]["client_id"]))
    res = await browser.get("/auth/google/callback", params={"code": "c", "state": ctx["state"]})
    assert res.status_code == 422 and "not registered" in res.text


async def test_bad_links_and_unknown_providers_get_pages_with_a_trace(browser: httpx.AsyncClient) -> None:
    for path, status, code in (
        ("/auth/sign-in?request=forged.0", 422, "E_INVALID"),
        ("/auth/sign-in", 422, "E_INVALID"),
        ("/auth/microsoft/start?request=x", 404, "E_NOT_FOUND"),
        ("/auth/probe-crash", 500, "E_INTERNAL"),
    ):
        res = await browser.get(path)
        assert res.status_code == status and code in res.text and "trace" in res.text, path
        assert "page internals" not in res.text


async def test_a_consent_from_an_earlier_sign_in_in_this_browser_is_refused(browser: httpx.AsyncClient) -> None:
    first, _ = await _to_allow(browser)
    await _to_allow(browser)
    res = await browser.post("/auth/allow", data={"consent": _consent(first), "decision": "allow"})
    assert res.status_code == 422 and "Start again" in res.text
