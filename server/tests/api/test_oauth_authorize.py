"""The authorization request in a browser: an unknown client or redirect URI is a page, never a redirect; anything
else wrong goes back to the client with the state and issuer; signing in with the provider leads to the Allow page,
whose answer goes back as a code or access_denied, from the browser that started it only."""

import re
from collections.abc import AsyncIterator
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import OAuthClient, OAuthCode
from glyphh_server.ops.auth import signed
from glyphh_server.ops.auth.secrets import hash_secret
from tests.api.browser import Browser, open_browser
from tests.conftest import PUBLIC_URL, SECRET_KEY, SETTINGS
from tests.connector import ask, query, register, to_allow
from tests.fakes import FakeStripe


@pytest.fixture
async def browser(engine: AsyncEngine, stripe: FakeStripe) -> AsyncIterator[Browser]:
    async for b in open_browser(stripe):
        yield b


async def test_an_unknown_client_or_return_address_is_a_page_not_a_redirect(browser: Browser) -> None:
    claude = await register(browser.http)
    for params in (
        ask(claude, client_id="not-a-uuid"),
        ask(claude, client_id="00000000-0000-0000-0000-000000000000"),
        ask(claude, redirect_uri="https://evil.test/cb"),
        ask(claude, redirect_uri=None),
    ):
        res = await browser.http.get("/oauth/authorize", params=params)
        assert res.status_code == 422 and "text/html" in res.headers["content-type"], params
        assert "location" not in res.headers and "E_INVALID" in res.text


@pytest.mark.parametrize(
    ("over", "error"),
    [
        ({"response_type": "token"}, "unsupported_response_type"),
        ({"state": None}, "invalid_request"),
        ({"code_challenge": None}, "invalid_request"),
        ({"code_challenge_method": "plain"}, "invalid_request"),
        ({"code_challenge": "short"}, "invalid_request"),
        ({"scope": "account admin"}, "invalid_scope"),
        ({"resource": "https://other.test/mcp"}, "invalid_target"),
    ],
)
async def test_any_other_refusal_goes_back_to_the_client(browser: Browser, over: dict, error: str) -> None:
    claude = await register(browser.http, redirect_uris=["https://claude.ai/cb?keep=1"])
    back = query(await browser.http.get("/oauth/authorize", params=ask(claude, **over)))
    assert (back["error"], back["iss"], back["keep"]) == (error, PUBLIC_URL, "1")
    assert back["error_description"]
    assert back.get("state") == (None if "state" in over else "st-1")


async def test_a_client_that_registered_only_for_refresh_is_unauthorized(browser: Browser) -> None:
    claude = await register(browser.http, grant_types=["refresh_token"])
    back = query(await browser.http.get("/oauth/authorize", params=ask(claude)))
    assert back["error"] == "unauthorized_client"


async def test_the_page_names_the_client_and_the_allow_page_its_host_and_the_person(browser: Browser) -> None:
    claude = await register(browser.http)
    page = await browser.http.get("/oauth/authorize", params=ask(claude, scope=None, resource=PUBLIC_URL))
    assert "Claude wants to use your Glyphh account" in page.text
    assert "Continue with Google" in page.text and "Continue with GitHub" in page.text
    allow, _ = await to_allow(browser.http, ask(claude))
    assert "Allow Claude to use your Glyphh account?" in allow
    assert f"Signed in as {browser.email}" in allow and "returns to claude.ai" in allow


async def test_allow_hands_a_code_for_this_request_and_deny_says_access_denied(
    browser: Browser, engine: AsyncEngine
) -> None:
    claude = await register(browser.http)
    _, consent = await to_allow(browser.http, ask(claude))
    back = query(await browser.http.post("/auth/oauth/allow", data={"consent": consent, "decision": "allow"}))
    assert set(back) == {"code", "state", "iss"}
    async with engine.connect() as conn:
        code = (await conn.execute(select(OAuthCode).where(OAuthCode.code_hash == hash_secret(back["code"])))).one()
    assert (str(code.client_id), code.scope, code.resource) == (claude["client_id"], "account", f"{PUBLIC_URL}/mcp")
    assert code.used_at is None and code.grant_id is None
    _, consent = await to_allow(browser.http, ask(claude, state="st-2"))
    denied = await browser.http.post("/auth/oauth/allow", data={"consent": consent, "decision": "deny"})
    assert query(denied) == {"error": "access_denied", "state": "st-2", "iss": PUBLIC_URL}
    assert 'glyphh_signin=""' in denied.headers["set-cookie"]


async def test_the_allow_form_works_only_in_the_browser_that_started_it_and_only_as_signed(
    browser: Browser, stripe: FakeStripe
) -> None:
    claude = await register(browser.http)
    _, consent = await to_allow(browser.http, ask(claude))
    async for other in open_browser(stripe):
        stolen = await other.http.post("/auth/oauth/allow", data={"consent": consent, "decision": "allow"})
        assert stolen.status_code == 422 and "location" not in stolen.headers
    wrong = signed.sign(SECRET_KEY, {"k": "link", "q": {}, "u": "x", "n": "y"}, 60)
    res = await browser.http.post("/auth/oauth/allow", data={"consent": wrong, "decision": "allow"})
    assert res.status_code == 422
    forged = await browser.http.get("/auth/google/start", params={"oauth": signed.sign(SECRET_KEY, {"k": "x"}, 60)})
    assert forged.status_code == 422


async def test_without_providers_the_page_says_so(engine: AsyncEngine, stripe: FakeStripe) -> None:
    async for bare in open_browser(stripe, SETTINGS):
        claude = await register(bare.http)
        page = await bare.http.get("/oauth/authorize", params=ask(claude))
        assert "No sign-in provider is set up" in page.text


async def test_github_leads_to_the_same_allow_page(browser: Browser, engine: AsyncEngine) -> None:
    claude = await register(browser.http)
    allow, _ = await to_allow(browser.http, ask(claude), "github")
    assert "Signed in as octo@gh.test" in allow
    async with engine.connect() as conn:
        assert (await conn.execute(select(OAuthClient.name).where(OAuthClient.id == claude["client_id"]))).scalar_one()
    page = await browser.http.get("/oauth/authorize", params=ask(claude))
    href = unescape(re.findall(r'href="([^"]+)"', page.text)[0])
    assert parse_qs(urlsplit(href).query)["oauth"]
