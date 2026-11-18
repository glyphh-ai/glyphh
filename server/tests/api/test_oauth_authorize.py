"""The authorization request in a browser: an unknown client or redirect URI is a refusal here, never a redirect;
anything else wrong goes back to the client with the state and issuer; a good request goes to the platform's
authorize page, signing in with the provider to its Allow page, whose answer goes back as a code or access_denied,
from the browser that started it only."""

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import OAuthCode
from glyphh_server.ops.auth import signed
from glyphh_server.ops.auth.secrets import hash_secret
from tests.api.browser import Browser, error_page, open_browser, staffed, went
from tests.conftest import PLATFORM_ID, PUBLIC_URL, SECRET_KEY, SETTINGS, _client
from tests.fakes import GITHUB_EMAILS, FakeStripe, fake_http
from tests.oauth import REDIRECT, RESOURCE, allow, ask, client_row, query, to_allow

KEPT: str = "https://claude.ai/cb?keep=1"


async def test_an_unknown_client_or_return_address_is_a_page_not_a_redirect(browser: Browser) -> None:
    for params, reason in (
        (ask(client_id="not-a-uuid"), "unknown_client"),
        (ask(client_id="00000000-0000-0000-0000-000000000000"), "unknown_client"),
        (ask(client_id=None), "unknown_client"),
        (ask(redirect_uri="https://evil.test/cb"), "redirect_uri"),
        (ask(redirect_uri=None), "redirect_uri"),
    ):
        res = await browser.http.get("/oauth/authorize", params=params)
        assert res.status_code == 422 and "location" not in res.headers, params
        assert (res.json()["error"]["code"], res.json()["error"]["reason"]) == ("E_INVALID", reason)


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
async def test_any_other_refusal_goes_back_to_the_client(
    browser: Browser, engine: AsyncEngine, over: dict, error: str
) -> None:
    for client in ({}, {"client_id": await client_row(engine, KEPT), "redirect_uri": KEPT}):
        res = await browser.http.get("/oauth/authorize", params=ask(**client, **over))
        assert res.headers["location"].startswith(client.get("redirect_uri", REDIRECT).split("?")[0] + "?")
        back = query(res)
        assert (back["error"], back["iss"], back.get("keep")) == (error, PUBLIC_URL, "1" if client else None)
        assert back["error_description"]
        assert back.get("state") == (None if "state" in over else "st-1")


async def test_an_address_that_is_not_the_servers_is_no_resource(browser: Browser) -> None:
    for bad in (
        "https://m1a2b3c4d5.glyphh.app",
        "https://m1a2b3c4d5.glyphh.app/mcp",
        f"{PUBLIC_URL}/mcp?x=1",
        f"{PUBLIC_URL}/v1",
    ):
        back = query(await browser.http.get("/oauth/authorize", params=ask(resource=bad)))
        assert back["error"] == "invalid_target", bad
    for good in (None, PUBLIC_URL, f"{PUBLIC_URL}/", "HTTP://LOCALHOST:8080/mcp/"):
        assert went(await browser.http.get("/oauth/authorize", params=ask(resource=good)))[0] == "/authorize", good


async def test_a_client_that_registered_only_for_refresh_is_unauthorized(browser: Browser, engine: AsyncEngine) -> None:
    only_refresh = await client_row(engine, KEPT, ["refresh_token"])
    res = await browser.http.get("/oauth/authorize", params=ask(client_id=only_refresh, redirect_uri=KEPT))
    assert query(res)["error"] == "unauthorized_client"


async def test_the_page_names_the_client_and_the_allow_page_its_host_and_the_person(browser: Browser) -> None:
    path, q = went(await browser.http.get("/oauth/authorize", params=ask(scope=None, resource=PUBLIC_URL)))
    assert (path, q["client"]) == ("/authorize", "Glyphh") and q["oauth"]
    shown, _ = await to_allow(browser.http, ask())
    assert shown == {
        "kind": "oauth",
        "client": "Glyphh",
        "returns_to": "localhost",
        "resource": RESOURCE,
        "email": browser.email,
    }


async def test_allow_hands_a_code_for_this_request_and_deny_says_access_denied(
    browser: Browser, engine: AsyncEngine
) -> None:
    _, consent = await to_allow(browser.http, ask())
    allowed = await allow(browser.http, consent, "allow")
    back = query(allowed)
    assert set(back) == {"code", "state", "iss"} and allowed.headers["location"].startswith(f"{REDIRECT}?")
    assert 'glyphh_signin=""' in allowed.headers["set-cookie"]
    async with engine.connect() as conn:
        code = (await conn.execute(select(OAuthCode).where(OAuthCode.code_hash == hash_secret(back["code"])))).one()
    assert (code.client_id, code.scope, code.resource) == (PLATFORM_ID, "account", RESOURCE)
    assert code.used_at is None and code.grant_id is None
    _, consent = await to_allow(browser.http, ask(state="st-2"))
    denied = await allow(browser.http, consent, "deny")
    assert query(denied) == {"error": "access_denied", "state": "st-2", "iss": PUBLIC_URL}
    assert 'glyphh_signin=""' in denied.headers["set-cookie"]
    gone = await allow(browser.http, consent, "allow")  # its cookie went with the answer
    assert "another browser" in error_page(gone)["message"]


async def test_the_allow_form_works_only_in_the_browser_that_started_it_and_only_as_signed(
    browser: Browser, stripe: FakeStripe
) -> None:
    _, consent = await to_allow(browser.http, ask())
    async for other in open_browser(stripe):
        assert "another browser" in error_page(await allow(other.http, consent, "allow"))["message"]
        await to_allow(other.http, ask())  # a sign-in of its own: still not this consent's browser
        assert "another browser" in error_page(await allow(other.http, consent, "allow"))["message"]
        read = await other.http.get("/auth/consent", params={"consent": consent})
        assert read.status_code == 422 and "another browser" in read.json()["error"]["message"]
    wrong = signed.sign(SECRET_KEY, {"k": "link", "q": {}, "u": "x", "n": "y"}, 60)
    assert error_page(await allow(browser.http, wrong, "allow"))["code"] == "E_INVALID"
    assert (await browser.http.get("/auth/consent", params={"consent": wrong})).status_code == 422
    assert "not valid" in error_page(await allow(browser.http, consent + "x", "allow"))["message"]


async def _started(http: httpx.AsyncClient) -> str:
    """Off to Google for the platform's request: the state it will come back with."""
    _, q = went(await http.get("/oauth/authorize", params=ask()))
    started = await http.get("/auth/google/start", params={"oauth": q["oauth"]})
    away = urlsplit(started.headers["location"])
    assert (away.netloc, started.status_code) == ("accounts.google.com", 302)
    cookie = started.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/auth" in cookie and "secure" not in cookie
    return parse_qs(away.query)["state"][0]


async def test_the_provider_step_starts_only_from_a_signed_request(browser: Browser) -> None:
    forged = await browser.http.get("/auth/google/start", params={"oauth": signed.sign(SECRET_KEY, {"k": "x"}, 60)})
    assert error_page(forged)["code"] == "E_INVALID" and "Start again" in error_page(forged)["message"]
    for params in ({}, {"oauth": ""}):
        assert "Start again" in error_page(await browser.http.get("/auth/google/start", params=params))["message"]
    unsigned = await browser.http.get("/auth/google/start", params={"oauth": "abc.def"})
    assert error_page(unsigned)["code"] == "E_INVALID"
    unknown = await browser.http.get("/auth/microsoft/start", params={"oauth": "x"})
    assert error_page(unknown)["code"] == "E_NOT_FOUND"


async def test_the_way_back_from_the_provider_is_this_browsers_this_providers_and_this_requests(
    browser: Browser, stripe: FakeStripe
) -> None:
    state = await _started(browser.http)
    back = {"code": "c-1", "state": state}
    async for other in open_browser(stripe):
        assert "another browser" in error_page(await other.http.get("/auth/google/callback", params=back))["message"]
        await _started(other.http)
        assert "another browser" in error_page(await other.http.get("/auth/google/callback", params=back))["message"]
    assert error_page(await browser.http.get("/auth/github/callback", params=back))["code"] == "E_INVALID"
    held = signed.verify(SECRET_KEY, state)
    assert (held["k"], held["p"], held["q"]["client_id"]) == ("oauth", "google", str(PLATFORM_ID))
    other_kind = signed.sign(SECRET_KEY, {**held, "k": "device"}, 60)
    refused = await browser.http.get("/auth/google/callback", params={"code": "c-1", "state": other_kind})
    assert "Start again" in error_page(refused)["message"]
    elsewhere = signed.sign(SECRET_KEY, {**held, "p": "microsoft"}, 60)
    unknown = await browser.http.get("/auth/microsoft/callback", params={"code": "c-1", "state": elsewhere})
    assert error_page(unknown)["code"] == "E_NOT_FOUND"
    cancelled = error_page(await browser.http.get("/auth/google/callback", params={"state": state}))
    assert cancelled["code"] == "E_FORBIDDEN" and "cancelled" in cancelled["message"]
    assert went(await browser.http.get("/auth/google/callback", params=back))[0] == "/allow"


async def test_without_providers_the_page_says_so(engine: AsyncEngine, stripe: FakeStripe) -> None:
    async for bare in open_browser(stripe, SETTINGS):
        path, q = went(await bare.http.get("/oauth/authorize", params=ask()))
        assert path == "/authorize"
        assert (await bare.http.get("/auth/providers")).json() == {"providers": [], "sso": False}
        refused = await bare.http.get("/auth/google/start", params={"oauth": q["oauth"]})
        assert error_page(refused)["code"] == "E_NOT_FOUND"


async def test_the_providers_offered_are_the_ones_configured_and_never_single_sign_on(browser: Browser) -> None:
    assert (await browser.http.get("/auth/providers")).json() == {"providers": ["google", "github"], "sso": False}


async def test_github_leads_to_the_same_allow_page(engine: AsyncEngine, stripe: FakeStripe) -> None:
    email = GITHUB_EMAILS[1]["email"]
    async for http in _client(create_app(staffed(email), http=fake_http(stripe))):
        shown, _ = await to_allow(http, ask(), "github")
        assert (shown["email"], shown["client"]) == (email, "Glyphh")
