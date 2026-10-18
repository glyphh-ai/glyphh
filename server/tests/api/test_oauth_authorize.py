"""The authorization request in a browser: an unknown client or redirect URI is a refusal here, never a redirect;
anything else wrong goes back to the client with the state and issuer; a good request goes to the platform's
authorize page, signing in with the provider to its Allow page, whose answer goes back as a code or access_denied,
from the browser that started it only."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import OAuthClient, OAuthCode
from glyphh_server.ops.auth import signed
from glyphh_server.ops.auth.secrets import hash_secret
from tests.api.browser import Browser, error_page, open_browser, went
from tests.conftest import PUBLIC_URL, SECRET_KEY, SETTINGS
from tests.connector import allow, ask, exchange, query, register, to_allow
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
        assert res.status_code == 422 and "location" not in res.headers, params
        assert res.json()["error"]["code"] == "E_INVALID"


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


async def test_a_hosted_runtimes_address_is_a_resource_too_bound_to_its_mcp(browser: Browser) -> None:
    claude = await register(browser.http)
    shown, consent = await to_allow(browser.http, ask(claude, resource="https://m1a2b3c4d5.glyphh.app"))
    assert shown["resource"] == "https://m1a2b3c4d5.glyphh.app/mcp"
    back = query(await allow(browser.http, consent, "allow"))
    res = await exchange(browser.http, claude, back["code"], resource="https://m1a2b3c4d5.glyphh.app/mcp")
    assert res.status_code == 200, res.text
    for bad in (
        "https://m1a2b3c4d5.glyphh.app/other",
        "http://m1a2b3c4d5.glyphh.app/mcp",
        "https://m1a2b3c4d5.evil.app/mcp",
        "https://no.glyphh.app/mcp",
        "https://m1a2b3c4d5.glyphh.app/mcp?x=1",
    ):
        back = query(await browser.http.get("/oauth/authorize", params=ask(claude, resource=bad)))
        assert back["error"] == "invalid_target", bad


async def test_a_client_that_registered_only_for_refresh_is_unauthorized(browser: Browser) -> None:
    claude = await register(browser.http, grant_types=["refresh_token"])
    back = query(await browser.http.get("/oauth/authorize", params=ask(claude)))
    assert back["error"] == "unauthorized_client"


async def test_the_page_names_the_client_and_the_allow_page_its_host_and_the_person(browser: Browser) -> None:
    claude = await register(browser.http)
    path, q = went(await browser.http.get("/oauth/authorize", params=ask(claude, scope=None, resource=PUBLIC_URL)))
    assert (path, q["client"]) == ("/authorize", "Claude") and q["oauth"]
    shown, _ = await to_allow(browser.http, ask(claude))
    assert shown == {
        "kind": "oauth",
        "client": "Claude",
        "returns_to": "claude.ai",
        "resource": f"{PUBLIC_URL}/mcp",
        "email": browser.email,
    }


async def test_allow_hands_a_code_for_this_request_and_deny_says_access_denied(
    browser: Browser, engine: AsyncEngine
) -> None:
    claude = await register(browser.http)
    _, consent = await to_allow(browser.http, ask(claude))
    back = query(await allow(browser.http, consent, "allow"))
    assert set(back) == {"code", "state", "iss"}
    async with engine.connect() as conn:
        code = (await conn.execute(select(OAuthCode).where(OAuthCode.code_hash == hash_secret(back["code"])))).one()
    assert (str(code.client_id), code.scope, code.resource) == (claude["client_id"], "account", f"{PUBLIC_URL}/mcp")
    assert code.used_at is None and code.grant_id is None
    _, consent = await to_allow(browser.http, ask(claude, state="st-2"))
    denied = await allow(browser.http, consent, "deny")
    assert query(denied) == {"error": "access_denied", "state": "st-2", "iss": PUBLIC_URL}
    assert 'glyphh_signin=""' in denied.headers["set-cookie"]


async def test_the_allow_form_works_only_in_the_browser_that_started_it_and_only_as_signed(
    browser: Browser, stripe: FakeStripe
) -> None:
    claude = await register(browser.http)
    _, consent = await to_allow(browser.http, ask(claude))
    async for other in open_browser(stripe):
        assert "another browser" in error_page(await allow(other.http, consent, "allow"))["message"]
    wrong = signed.sign(SECRET_KEY, {"k": "link", "q": {}, "u": "x", "n": "y"}, 60)
    assert error_page(await allow(browser.http, wrong, "allow"))["code"] == "E_INVALID"
    _, consent = await to_allow(browser.http, ask(claude))  # an Allow consent is not a device approval
    assert (
        error_page(await browser.http.get("/auth/approve", params={"consent": consent, "decision": "approve"}))["code"]
        == "E_INVALID"
    )
    forged = await browser.http.get("/auth/google/start", params={"oauth": signed.sign(SECRET_KEY, {"k": "x"}, 60)})
    assert error_page(forged)["code"] == "E_INVALID"


async def test_without_providers_the_page_says_so(engine: AsyncEngine, stripe: FakeStripe) -> None:
    async for bare in open_browser(stripe, SETTINGS):
        claude = await register(bare.http)
        assert went(await bare.http.get("/oauth/authorize", params=ask(claude)))[0] == "/authorize"
        assert (await bare.http.get("/auth/providers")).json() == {"providers": []}


async def test_github_leads_to_the_same_allow_page(browser: Browser, engine: AsyncEngine) -> None:
    claude = await register(browser.http)
    shown, _ = await to_allow(browser.http, ask(claude), "github")
    assert shown["email"] == "octo@gh.test"
    async with engine.connect() as conn:
        assert (await conn.execute(select(OAuthClient.name).where(OAuthClient.id == claude["client_id"]))).scalar_one()
