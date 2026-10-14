"""Signing an install in by device flow (RFC 8628): the mod's calls and the person's page."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import DeviceCode
from tests.api.browser import Browser, new_code, open_browser, sign_in, to_approve
from tests.conftest import SETTINGS
from tests.fakes import FakeStripe


@pytest.fixture
async def browser(engine: AsyncEngine, stripe: FakeStripe) -> AsyncIterator[Browser]:
    async for b in open_browser(stripe):
        yield b


async def _poll(http: httpx.AsyncClient, device_code: str) -> httpx.Response:
    return await http.post("/v1/device/token", json={"device_code": device_code})


def _code(res: httpx.Response) -> str:
    assert res.status_code == 400, res.text
    return res.json()["error"]["code"]


async def _age(engine: AsyncEngine, user_code: str, **values: object) -> None:
    async with engine.begin() as conn:
        await conn.execute(update(DeviceCode).where(DeviceCode.user_code == user_code).values(**values))


async def test_signing_in_makes_an_install_with_a_free_org_and_hands_its_token_once(browser: Browser) -> None:
    code = await new_code(browser.http, "Ada's Mac", "cli")
    assert code["verification_uri"] == "http://localhost:8080/v1/device"
    assert code["verification_uri_complete"].endswith(f"?code={code['user_code']}")
    assert (code["interval"], code["expires_in"], len(code["user_code"])) == (5, 600, 9)
    page = await browser.http.get("/v1/device", params={"code": code["user_code"].lower().replace("-", "")})
    assert (
        code["user_code"] in page.text and "Continue with Google" in page.text and "Continue with GitHub" in page.text
    )
    shown, consent = await to_approve(browser.http, code["user_code"])
    assert "Ada&#x27;s Mac (cli)" in shown.text and browser.email in shown.text
    done = await browser.http.post("/auth/approve", data={"consent": consent, "decision": "approve"})
    assert "Signed in. Go back to Claude." in done.text and 'glyphh_signin=""' in done.headers["set-cookie"]
    token = (await _poll(browser.http, code["device_code"])).json()
    assert token["token_type"] == "Bearer" and token["install_id"]
    me = (await browser.http.get("/v1/me", headers={"authorization": f"Bearer {token['access_token']}"})).json()
    assert (me["email"], me["role"], me["plan"]["name"], me["providers"]) == (
        browser.email,
        "admin",
        "Free",
        ["google"],
    )
    assert _code(await _poll(browser.http, code["device_code"])) == "expired_token"


async def test_polling_waits_and_too_fast_is_told_to_slow_down(browser: Browser, engine: AsyncEngine) -> None:
    code = await new_code(browser.http)
    assert _code(await _poll(browser.http, code["device_code"])) == "authorization_pending"
    slow = await _poll(browser.http, code["device_code"])
    assert _code(slow) == "slow_down" and "10 seconds" in slow.json()["error"]["message"]
    async with engine.connect() as conn:
        found = select(DeviceCode.interval).where(DeviceCode.user_code == code["user_code"])
        assert (await conn.execute(found)).scalar_one() == 10
    await _age(engine, code["user_code"], polled_at=datetime.now(UTC) - timedelta(minutes=1))
    assert _code(await _poll(browser.http, code["device_code"])) == "authorization_pending"


async def test_a_denied_sign_in_says_so_once(browser: Browser) -> None:
    code = await new_code(browser.http)
    _, consent = await to_approve(browser.http, code["user_code"])
    done = await browser.http.post("/auth/approve", data={"consent": consent, "decision": "deny"})
    assert "Nothing was signed in" in done.text
    assert _code(await _poll(browser.http, code["device_code"])) == "access_denied"
    assert _code(await _poll(browser.http, code["device_code"])) == "expired_token"
    again = await browser.http.post("/auth/approve", data={"consent": consent, "decision": "deny"})
    assert again.status_code == 422 and "expired" in again.text


async def test_an_expired_or_unknown_code_is_expired(browser: Browser, engine: AsyncEngine) -> None:
    code = await new_code(browser.http)
    await _age(engine, code["user_code"], expires_at=datetime.now(UTC) - timedelta(seconds=1))
    page = await browser.http.get("/v1/device", params={"code": code["user_code"]})
    assert page.status_code == 422 and "Start again in Claude" in page.text
    assert _code(await _poll(browser.http, code["device_code"])) == "expired_token"
    assert _code(await _poll(browser.http, "never-issued")) == "expired_token"


async def test_old_codes_are_cleared_when_a_new_one_starts(browser: Browser, engine: AsyncEngine) -> None:
    old = await new_code(browser.http)
    await _age(engine, old["user_code"], expires_at=datetime.now(UTC) - timedelta(hours=1))
    await new_code(browser.http)
    async with engine.connect() as conn:
        found = select(DeviceCode.user_code).where(DeviceCode.user_code == old["user_code"])
        assert (await conn.execute(found)).first() is None


async def test_the_page_asks_for_the_code_when_the_link_has_none(browser: Browser) -> None:
    page = await browser.http.get("/v1/device")
    assert page.status_code == 200 and '<input name="code"' in page.text


async def test_without_providers_the_page_says_so(engine: AsyncEngine, stripe: FakeStripe) -> None:
    async for bare in open_browser(stripe, SETTINGS):
        code = await new_code(bare.http)
        page = await bare.http.get("/v1/device", params={"code": code["user_code"]})
        assert "No sign-in provider is set up" in page.text and "Continue with" not in page.text


async def test_an_install_past_the_plan_is_refused_and_the_code_keeps_waiting(browser: Browser) -> None:
    await sign_in(browser.http)
    code = await new_code(browser.http, "Second machine")
    _, consent = await to_approve(browser.http, code["user_code"])
    refused = await browser.http.post("/auth/approve", data={"consent": consent, "decision": "approve"})
    assert refused.status_code == 403 and "allows 1 installs" in refused.text and "E_LIMIT" in refused.text
    assert _code(await _poll(browser.http, code["device_code"])) == "authorization_pending"


async def test_github_signs_in_the_same_way(browser: Browser) -> None:
    headers = await sign_in(browser.http, "github")
    me = (await browser.http.get("/v1/me", headers=headers)).json()
    assert (me["email"], me["name"], me["providers"]) == ("octo@gh.test", "Octo Cat", ["github"])


async def test_steps_from_another_browser_or_a_crossed_provider_are_refused(
    browser: Browser, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    code = await new_code(browser.http)
    started = await browser.http.get("/auth/google/start", params={"code": code["user_code"]})
    state = started.headers["location"].split("state=")[1].split("&")[0]
    crossed = await browser.http.get("/auth/github/callback", params={"code": "c", "state": state})
    assert crossed.status_code == 422 and "Start again" in crossed.text
    cancelled = await browser.http.get("/auth/google/callback", params={"state": state, "error": "access_denied"})
    assert cancelled.status_code == 403 and "cancelled" in cancelled.text
    _, consent = await to_approve(browser.http, code["user_code"])
    async for stranger in open_browser(stripe):
        for res in (
            await stranger.http.post("/auth/approve", data={"consent": consent, "decision": "approve"}),
            await stranger.http.get("/auth/google/callback", params={"code": "c", "state": state}),
        ):
            assert res.status_code == 422 and "another browser" in res.text
    other = await new_code(browser.http)
    await to_approve(browser.http, other["user_code"])
    stale = await browser.http.post("/auth/approve", data={"consent": consent, "decision": "approve"})
    assert stale.status_code == 422 and "another browser" in stale.text


async def test_bad_steps_land_on_a_page_with_a_trace(browser: Browser, engine: AsyncEngine) -> None:
    code = await new_code(browser.http)
    started = await browser.http.get("/auth/google/start", params={"code": code["user_code"]})
    state = started.headers["location"].split("state=")[1].split("&")[0]
    await _age(engine, code["user_code"], expires_at=datetime.now(UTC) - timedelta(seconds=1))
    for path, status in (
        (f"/auth/google/callback?code=c&state={state}", 422),
        ("/auth/microsoft/start?code=x", 404),
        ("/auth/google/start?code=BBBB-BBBB", 422),
        ("/auth/google/callback?code=c&state=forged.0", 422),
        ("/auth/google/start", 422),
    ):
        res = await browser.http.get(path)
        assert res.status_code == status and "trace" in res.text and res.headers["x-request-id"] in res.text, path


async def test_the_device_calls_check_their_input(browser: Browser) -> None:
    for body in (
        {"name": "", "surface": "cli", "mod_version": "1"},
        {"name": "x", "surface": "tv", "mod_version": "1"},
    ):
        res = await browser.http.post("/v1/device/code", json=body)
        assert res.status_code == 422 and res.json()["error"]["code"] == "E_INVALID"
