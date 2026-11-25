"""Signing an install in by device flow (RFC 8628): the mod's calls and the person's page."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import DeviceCode
from tests.api.browser import Browser, decide, error_page, new_code, open_browser, sign_in, to_approve, went
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
    assert went(page) == ("/device", {"code": code["user_code"]})
    assert (await browser.http.get("/auth/providers")).json()["providers"] == ["google", "github"]
    shown, consent = await to_approve(browser.http, code["user_code"])
    assert shown == {
        "kind": "device",
        "code": code["user_code"],
        "name": "Ada's Mac",
        "surface": "cli",
        "email": browser.email,
    }
    done = await decide(browser.http, consent, "approve")
    assert went(done) == ("/device/done", {"result": "approved"}) and 'glyphh_signin=""' in done.headers["set-cookie"]
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
    assert went(await decide(browser.http, consent, "deny")) == ("/device/done", {"result": "denied"})
    assert _code(await _poll(browser.http, code["device_code"])) == "access_denied"
    assert _code(await _poll(browser.http, code["device_code"])) == "expired_token"
    again = error_page(await decide(browser.http, consent, "deny"))
    assert again["code"] == "E_INVALID" and "expired" in again["message"]


async def test_an_expired_or_unknown_code_is_expired(browser: Browser, engine: AsyncEngine) -> None:
    code = await new_code(browser.http)
    await _age(engine, code["user_code"], expires_at=datetime.now(UTC) - timedelta(seconds=1))
    page = error_page(await browser.http.get("/v1/device", params={"code": code["user_code"]}))
    assert page["code"] == "E_INVALID" and "Start again in Claude" in page["message"]
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
    assert went(await browser.http.get("/v1/device")) == ("/device", {})


async def test_without_providers_the_page_says_so(engine: AsyncEngine, stripe: FakeStripe) -> None:
    async for bare in open_browser(stripe, SETTINGS):
        code = await new_code(bare.http)
        assert went(await bare.http.get("/v1/device", params={"code": code["user_code"]}))[0] == "/device"
        assert (await bare.http.get("/auth/providers")).json()["providers"] == []


async def test_installs_are_never_limited_a_second_machine_is_a_second_install(browser: Browser) -> None:
    await sign_in(browser.http)
    code = await new_code(browser.http, "Second machine")
    _, consent = await to_approve(browser.http, code["user_code"])
    await decide(browser.http, consent, "approve")
    token = (await _poll(browser.http, code["device_code"])).json()["access_token"]
    installs = (await browser.http.get("/v1/installs", headers={"authorization": f"Bearer {token}"})).json()
    assert "Second machine" in [i["name"] for i in installs] and len(installs) == 2


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
    crossed = error_page(await browser.http.get("/auth/github/callback", params={"code": "c", "state": state}))
    assert crossed["code"] == "E_INVALID" and "Start again" in crossed["message"]
    cancelled = error_page(
        await browser.http.get("/auth/google/callback", params={"state": state, "error": "access_denied"})
    )
    assert cancelled["code"] == "E_FORBIDDEN" and "cancelled" in cancelled["message"]
    _, consent = await to_approve(browser.http, code["user_code"])
    async for stranger in open_browser(stripe):
        for res in (
            await decide(stranger.http, consent, "approve"),
            await stranger.http.get("/auth/google/callback", params={"code": "c", "state": state}),
        ):
            assert "another browser" in error_page(res)["message"]
        read = await stranger.http.get("/auth/consent", params={"consent": consent})
        assert read.status_code == 422 and "another browser" in read.json()["error"]["message"]
    other = await new_code(browser.http)
    await to_approve(browser.http, other["user_code"])
    assert "another browser" in error_page(await decide(browser.http, consent, "approve"))["message"]


async def test_bad_steps_land_on_a_page_with_a_trace(browser: Browser, engine: AsyncEngine) -> None:
    code = await new_code(browser.http)
    started = await browser.http.get("/auth/google/start", params={"code": code["user_code"]})
    state = started.headers["location"].split("state=")[1].split("&")[0]
    await _age(engine, code["user_code"], expires_at=datetime.now(UTC) - timedelta(seconds=1))
    for path, code_ in (
        (f"/auth/google/callback?code=c&state={state}", "E_INVALID"),
        ("/auth/microsoft/start?code=x", "E_NOT_FOUND"),
        ("/auth/google/start?code=BBBB-BBBB", "E_INVALID"),
        ("/auth/google/callback?code=c&state=forged.0", "E_INVALID"),
        ("/auth/google/start", "E_INVALID"),
    ):
        assert error_page(await browser.http.get(path))["code"] == code_, path


async def test_the_device_calls_check_their_input(browser: Browser) -> None:
    for body in (
        {"name": "", "surface": "cli", "mod_version": "1"},
        {"name": "x", "surface": "tv", "mod_version": "1"},
    ):
        res = await browser.http.post("/v1/device/code", json=body)
        assert res.status_code == 422 and res.json()["error"]["code"] == "E_INVALID"
