"""A member signs in for an agent host the way a browser does it: the platform's screens, the server's steps."""

from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import OAuthClient
from glyphh_server.ops.auth import signed
from tests.conftest import PLATFORM_URL, SECRET_KEY, _client
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


EXPIRED = signed.sign(SECRET_KEY, {"c": "x"}, -1)


def screen(res: httpx.Response, path: str) -> dict[str, str]:
    """The browser was sent to this platform screen; its query, one value each."""
    assert res.status_code == 303, res.text
    to = urlsplit(res.headers["location"])
    assert f"{to.scheme}://{to.netloc}{to.path}" == f"{PLATFORM_URL}{path}"
    return {k: v[0] for k, v in parse_qs(to.query).items()}


async def _to_allow(browser: httpx.AsyncClient, provider: str = "google") -> tuple[str, dict]:
    host = await _register(browser, token_endpoint_auth_method="none", client_name="Claude")
    verifier, challenge = _pkce()
    params = {"response_type": "code", "client_id": host["client_id"], "redirect_uri": REDIRECT, "state": "st-9"}
    authorize = await browser.get(
        "/authorize", params={**params, "code_challenge": challenge, "code_challenge_method": "S256"}
    )
    link = urlsplit(authorize.headers["location"])
    assert f"{link.scheme}://{link.netloc}{link.path}" == f"{PLATFORM_URL}/sign-in"
    token = parse_qs(link.query)["request"][0]
    shown = await browser.get("/v1/auth/sign-in", params={"request": token})
    assert shown.json() == {"providers": ["google", "github"]}
    started = await browser.get(f"/auth/{provider}/start", params={"request": token})
    assert started.status_code == 302 and "glyphh_signin" in started.headers["set-cookie"]
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    back = await browser.get(f"/auth/{provider}/callback", params={"code": "c-1", "state": state})
    consent = screen(back, "/allow")["consent"]
    return consent, {"host": host, "verifier": verifier, "state": state}


async def test_signing_in_with_google_and_allowing_gives_the_host_a_code(browser: httpx.AsyncClient) -> None:
    consent, ctx = await _to_allow(browser)
    shown = (await browser.get("/v1/auth/allow", params={"consent": consent})).json()
    assert (shown["host"], shown["email"]) == ("Claude", "pages@google.test")
    assert (shown["orgs"][0]["name"], shown["orgs"][0]["personal"], shown["orgs"][0]["role"]) == (
        "Personal",
        True,
        "org_admin",
    )
    back = await browser.post("/auth/allow", data={"consent": consent, "decision": "allow"})
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
    consent, _ = await _to_allow(browser, "github")
    assert (await browser.get("/v1/auth/allow", params={"consent": consent})).json()["email"] == "octo@gh.test"
    back = await browser.post("/auth/allow", data={"consent": consent, "decision": "deny"})
    query = parse_qs(urlsplit(back.headers["location"]).query)
    assert back.status_code == 303 and query["error"] == ["access_denied"] and query["state"] == ["st-9"]


async def test_a_sign_in_from_another_browser_is_refused(browser: httpx.AsyncClient) -> None:
    consent, ctx = await _to_allow(browser)
    async for stranger in _client(
        create_app(PROVIDER_SETTINGS, http=httpx.AsyncClient(transport=provider_transport()))
    ):
        for res in (
            await stranger.post("/auth/allow", data={"consent": consent, "decision": "allow"}),
            await stranger.get("/auth/google/callback", params={"code": "c", "state": ctx["state"]}),
        ):
            problem = screen(res, "/problem")
            assert problem["code"] == "E_INVALID" and "Start again" in problem["message"] and problem["trace"]


async def test_a_cancelled_or_crossed_provider_sign_in_is_refused(browser: httpx.AsyncClient) -> None:
    _, ctx = await _to_allow(browser)
    cancelled = await browser.get("/auth/google/callback", params={"state": ctx["state"], "error": "access_denied"})
    assert screen(cancelled, "/problem") | {"message": "", "trace": ""} == {
        "code": "E_FORBIDDEN",
        "message": "",
        "trace": "",
        "reason": "cancelled",
    }
    crossed = await browser.get("/auth/github/callback", params={"code": "c", "state": ctx["state"]})
    assert screen(crossed, "/problem")["code"] == "E_INVALID"


async def test_a_host_removed_mid_sign_in_is_refused(browser: httpx.AsyncClient, engine: AsyncEngine) -> None:
    _, ctx = await _to_allow(browser)
    async with engine.begin() as conn:
        await conn.execute(delete(OAuthClient).where(OAuthClient.client_id == ctx["host"]["client_id"]))
    res = await browser.get("/auth/google/callback", params={"code": "c", "state": ctx["state"]})
    assert "not registered" in screen(res, "/problem")["message"]


async def test_bad_steps_land_on_the_problem_screen_with_a_trace(browser: httpx.AsyncClient) -> None:
    for path, code in (
        ("/auth/google/start?request=forged.0", "E_INVALID"),
        ("/auth/google/start?request=" + EXPIRED, "E_INVALID"),
        ("/auth/google/start", "E_INVALID"),
        ("/auth/microsoft/start?request=x", "E_NOT_FOUND"),
        ("/auth/google/callback", "E_INVALID"),
        ("/auth/probe-crash", "E_INTERNAL"),
    ):
        problem = screen(await browser.get(path), "/problem")
        assert problem["code"] == code and problem["trace"] and "page internals" not in problem["message"], path


async def test_the_screens_refuse_forged_values_in_json(browser: httpx.AsyncClient) -> None:
    for path in ("/v1/auth/sign-in?request=forged.0", "/v1/auth/sign-in", "/v1/auth/allow?consent=forged.0"):
        res = await browser.get(path)
        assert res.status_code == 422 and res.json()["error"]["code"] == "E_INVALID", path


async def test_a_consent_from_an_earlier_sign_in_in_this_browser_is_refused(browser: httpx.AsyncClient) -> None:
    first, _ = await _to_allow(browser)
    await _to_allow(browser)
    res = await browser.post("/auth/allow", data={"consent": first, "decision": "allow"})
    assert "Start again" in screen(res, "/problem")["message"]


async def test_only_the_platform_may_call_the_api_from_a_browser(browser: httpx.AsyncClient) -> None:
    ask = {"access-control-request-method": "GET", "access-control-request-headers": "authorization"}
    ok = await browser.options("/v1/me", headers={"origin": PLATFORM_URL, **ask})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == PLATFORM_URL
    other = await browser.options("/v1/me", headers={"origin": "https://evil.test", **ask})
    assert "access-control-allow-origin" not in other.headers


async def test_each_refusal_says_why_so_the_screen_can_show_it(browser: httpx.AsyncClient) -> None:
    expired = screen(await browser.get("/auth/google/start", params={"request": EXPIRED}), "/problem")
    forged = screen(await browser.get("/auth/google/start", params={"request": "forged.0"}), "/problem")
    assert (expired["reason"], forged["reason"]) == ("expired", "invalid")


async def test_the_host_acts_in_the_org_picked_under_use_with(browser: httpx.AsyncClient, engine: AsyncEngine) -> None:
    from sqlalchemy import insert, select

    from glyphh_server.models import Membership, Token, User
    from tests.db.helpers import make_org

    consent, ctx = await _to_allow(browser)
    async with engine.begin() as conn:
        me = (await conn.execute(select(User.id).where(User.email == "pages@google.test"))).scalar_one()
    team = await make_org(engine, "Use With Co")
    stranger = await make_org(engine, "Not Theirs Co")
    async with engine.begin() as conn:
        await conn.execute(insert(Membership).values(user_id=me, org_id=team, role="user"))
    names = [o["name"] for o in (await browser.get("/v1/auth/allow", params={"consent": consent})).json()["orgs"]]
    assert names[0] == "Personal" and "Use With Co" in names
    refused = await browser.post("/auth/allow", data={"consent": consent, "decision": "allow", "org": str(stranger)})
    assert screen(refused, "/problem")["reason"] == "not_a_member"
    consent, ctx = await _to_allow(browser)
    back = await browser.post("/auth/allow", data={"consent": consent, "decision": "allow", "org": str(team)})
    code = parse_qs(urlsplit(back.headers["location"]).query)["code"][0]
    body = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT}
    issued = await browser.post(
        "/token", data={**body, "client_id": ctx["host"]["client_id"], "code_verifier": ctx["verifier"]}
    )
    me_now = (await browser.get("/v1/me", headers={"authorization": f"Bearer {issued.json()['access_token']}"})).json()
    assert (me_now["org"]["name"], me_now["role"]) == ("Use With Co", "user")
    async with engine.connect() as conn:
        assert team in (await conn.execute(select(Token.org_id).where(Token.user_id == me))).scalars().all()


async def test_not_you_goes_back_to_the_sign_in_with_the_same_request(browser: httpx.AsyncClient) -> None:
    consent, _ = await _to_allow(browser)
    back = await browser.get("/auth/switch", params={"consent": consent})
    assert screen(back, "/sign-in")["request"] and "glyphh_signin=" in back.headers["set-cookie"]
