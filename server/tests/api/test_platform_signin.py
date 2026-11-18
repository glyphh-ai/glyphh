"""The platform signs in as an OAuth client, and only Glyphh's staff through it: its access token works on /v1 as
its person, nobody else signs in and nobody signs up, and it reads a consent from the browser with CORS for its own
origin only."""

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.api.browser_session import same_site
from glyphh_server.api.gone import RETIRED
from glyphh_server.app import create_app
from glyphh_server.models import Identity, User
from tests.api.browser import Browser, Staff, error_page, open_browser, went
from tests.conftest import PROVIDER_SETTINGS, SETTINGS, _client
from tests.db.helpers import granted, person
from tests.fakes import GOOGLE_ME, FakeStripe, fake_http
from tests.oauth import allow, ask, exchange, query, to_allow

PLATFORM: str = SETTINGS.platform_base


async def test_v1_takes_an_oauth_access_token_as_its_person(staff: Staff, engine: AsyncEngine) -> None:
    _, auth = await granted(engine, staff.who)
    me = await staff.http.get("/v1/me", headers=auth)
    assert me.status_code == 200, me.text
    assert (me.json()["email"], me.json()["org"]["id"]) == (staff.who.email, str(staff.who.org_id))


async def test_an_access_token_for_another_resource_is_refused_like_any_bad_token(
    staff: Staff, engine: AsyncEngine
) -> None:
    _, auth = await granted(engine, staff.who, resource="https://elsewhere.example/mcp")
    res = await staff.http.get("/v1/me", headers=auth)
    assert res.status_code == 401
    assert res.json()["error"]["message"] == "Sign in to Glyphh again: this token is not valid."


async def test_a_staff_member_new_to_glyphh_signs_in_and_gets_an_org_of_their_own(
    browser: Browser, engine: AsyncEngine
) -> None:
    _, consent = await to_allow(browser.http, ask())
    tokens = await exchange(browser.http, query(await allow(browser.http, consent, "allow"))["code"])
    assert tokens.status_code == 200, tokens.text
    me = (await browser.http.get("/v1/me", headers={"authorization": f"Bearer {tokens.json()['access_token']}"})).json()
    assert (me["email"], me["name"], me["role"], me["staff"]) == (browser.email, "Paige Turner", "admin", True)
    assert (me["org"]["name"], me["org"]["billing_status"]) == ("Paige Turner's org", "none")


async def _back_from_google(http: httpx.AsyncClient) -> httpx.Response:
    _, q = went(await http.get("/oauth/authorize", params=ask()))
    started = await http.get("/auth/google/start", params={"oauth": q["oauth"]})
    state = dict(httpx.URL(started.headers["location"]).params)["state"]
    return await http.get("/auth/google/callback", params={"code": "c-1", "state": state})


async def test_nobody_else_signs_in_and_nobody_signs_up(engine: AsyncEngine, stripe: FakeStripe) -> None:
    async for stranger in open_browser(stripe, staff=False):
        refused = error_page(await _back_from_google(stranger.http))
        assert (refused["code"], refused["message"]) == ("E_WOUND_DOWN", RETIRED)
        async with engine.connect() as conn:
            made = select(func.count()).select_from(User).where(func.lower(User.email) == stranger.email)
            assert (await conn.execute(made)).scalar_one() == 0
    known = await person(engine, "Team")  # a customer from before: their account is still there, but no way in
    over = {("GET", "/v1/userinfo"): {**GOOGLE_ME, "sub": f"g-{known.email}", "email": known.email.upper()}}
    async for http in _client(create_app(PROVIDER_SETTINGS, http=fake_http(stripe, over))):
        assert error_page(await _back_from_google(http))["code"] == "E_WOUND_DOWN"
    async with engine.connect() as conn:
        linked = select(func.count()).select_from(Identity).where(Identity.user_id == known.user_id)
        assert (await conn.execute(linked)).scalar_one() == 0


async def _consent(http: httpx.AsyncClient) -> str:
    _, consent = await to_allow(http, ask())
    return consent


async def test_the_platform_reads_a_consent_with_credentials(browser: Browser) -> None:
    consent = await _consent(browser.http)
    res = await browser.http.get("/auth/consent", params={"consent": consent}, headers={"origin": PLATFORM})
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == PLATFORM
    assert res.headers["access-control-allow-credentials"] == "true"
    assert "Origin" in res.headers["vary"]


async def test_a_refusal_carries_cors_too_so_the_platform_can_show_it(client: httpx.AsyncClient) -> None:
    res = await client.get("/auth/consent", params={"consent": "x"}, headers={"origin": f"{PLATFORM}/"})
    assert res.status_code == 422
    assert res.headers["access-control-allow-origin"] == PLATFORM


async def test_no_other_origin_or_path_gets_cors(browser: Browser) -> None:
    consent = await _consent(browser.http)
    for headers in ({"origin": "https://evil.example"}, {}):
        other = await browser.http.get("/auth/consent", params={"consent": consent}, headers=headers)
        assert other.status_code == 200 and "access-control-allow-origin" not in other.headers
        assert "access-control-allow-credentials" not in other.headers and "Origin" in other.headers["vary"]
    elsewhere = await browser.http.get("/auth/providers", headers={"origin": PLATFORM})
    assert "access-control-allow-origin" not in elsewhere.headers and "vary" not in elsewhere.headers


def test_the_signin_cookie_is_lax_on_one_site_and_none_across_sites() -> None:
    assert same_site(SETTINGS) == "lax"
    same = PROVIDER_SETTINGS.model_copy(
        update={"public_url": "https://api.glyphh.ai", "platform_url": "https://platform.glyphh.ai"}
    )
    assert same_site(same) == "lax"
    across = same.model_copy(update={"platform_url": "http://localhost:5173"})
    assert same_site(across) == "none"
    assert same_site(same.model_copy(update={"platform_url": "not a url"})) == "none"


async def test_the_cookie_is_sent_with_the_samesite_it_needs(engine: AsyncEngine) -> None:
    across = PROVIDER_SETTINGS.model_copy(
        update={"public_url": "https://tunnel.example.dev", "platform_url": "http://localhost:5173"}
    )
    async for c in _client(create_app(across, http=fake_http())):
        started = await c.get("/oauth/authorize", params=ask(resource=None))
        assert started.headers["location"].startswith("http://localhost:5173/authorize?")
        oauth = dict(httpx.URL(started.headers["location"]).params)["oauth"]
        res = await c.get("/auth/google/start", params={"oauth": oauth})
        cookie = res.headers["set-cookie"].lower()
        assert "samesite=none" in cookie and "secure" in cookie
        callback = dict(httpx.URL(res.headers["location"]).params)["redirect_uri"]
        assert callback == "https://tunnel.example.dev/auth/google/callback"
