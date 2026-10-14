"""An install is a machine: signing in again on the same machine reuses its install; a new machine counts."""

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import DeviceCode, Install, Token, User
from tests.api.browser import Browser, new_code, open_browser, sign_in, to_approve
from tests.fakes import FakeStripe

MAC: str = "c0ffee-hardware-uuid-hash_0123456789"


@pytest.fixture
async def browser(engine: AsyncEngine, stripe: FakeStripe) -> AsyncIterator[Browser]:
    async for b in open_browser(stripe):
        yield b


async def _installs(engine: AsyncEngine, email: str) -> list[tuple[str, str, str]]:
    async with engine.connect() as conn:
        rows = await conn.execute(
            select(Install.machine_id, Install.name, Install.mod_version)
            .join(User, User.id == Install.user_id)
            .where(User.email == email, Install.revoked_at.is_(None))
        )
        return [tuple(r) for r in rows]


async def _approve(http: httpx.AsyncClient, code: dict[str, str]) -> httpx.Response:
    _, consent = await to_approve(http, code["user_code"])
    return await http.post("/auth/approve", data={"consent": consent, "decision": "approve"})


async def test_signing_in_again_on_the_same_machine_reuses_its_install(browser: Browser, engine: AsyncEngine) -> None:
    first = await sign_in(browser.http, machine_id=MAC)
    again = await new_code(browser.http, "Ada's renamed Mac", machine_id=MAC)
    assert "Signed in" in (await _approve(browser.http, again)).text
    assert (await browser.http.get("/v1/me", headers=first)).status_code == 401
    token = (await browser.http.post("/v1/device/token", json={"device_code": again["device_code"]})).json()
    headers = {"authorization": f"Bearer {token['access_token']}"}
    me = (await browser.http.get("/v1/me", headers=headers)).json()
    assert me["used"]["installs"] == 1 and me["plan"]["limits"]["installs"] == 1
    listed = (await browser.http.get("/v1/installs", headers=headers)).json()
    assert [(i["id"], i["machine_id"], i["name"], i["current"]) for i in listed] == [
        (token["install_id"], MAC, "Ada's renamed Mac", True)
    ]
    assert listed[0]["last_seen_at"] is not None
    async with engine.connect() as conn:
        held = select(func.count()).where(Token.install_id == token["install_id"], Token.revoked_at.is_(None))
        assert (await conn.execute(held)).scalar_one() == 1


async def test_a_new_machine_past_the_plan_is_refused_and_revoking_frees_the_slot(browser: Browser) -> None:
    mac = await sign_in(browser.http, machine_id=MAC)
    other = await new_code(browser.http, "Linux box", machine_id="linux-box-machine-id-0001")
    refused = await _approve(browser.http, other)
    assert refused.status_code == 403 and "E_LIMIT" in refused.text and "allows 1 installs" in refused.text
    installs = (await browser.http.get("/v1/installs", headers=mac)).json()
    assert (await browser.http.delete(f"/v1/installs/{installs[0]['id']}", headers=mac)).status_code == 204
    assert "Signed in" in (await _approve(browser.http, other)).text
    back = await new_code(browser.http, machine_id=MAC)
    assert (await _approve(browser.http, back)).status_code == 403


async def test_an_old_mod_without_a_machine_id_gets_one_made_up(browser: Browser, engine: AsyncEngine) -> None:
    body = {"name": "Old Mac", "surface": "desktop", "mod_version": "0.0.9"}
    code = (await browser.http.post("/v1/device/code", json=body)).json()
    async with engine.connect() as conn:
        made = select(DeviceCode.machine_id).where(DeviceCode.user_code == code["user_code"])
        machine_id = (await conn.execute(made)).scalar_one()
    assert 16 <= len(machine_id) <= 128
    assert "Signed in" in (await _approve(browser.http, code)).text
    assert await _installs(engine, browser.email) == [(machine_id, "Old Mac", "0.0.9")]


async def test_a_machine_id_is_checked(browser: Browser) -> None:
    for machine_id in ("short", "x" * 129, "has spaces in it ok?", "slash/is/not/allowed/here", 12345678901234567):
        body = {"machine_id": machine_id, "name": "Mac", "surface": "desktop", "mod_version": "1"}
        res = await browser.http.post("/v1/device/code", json=body)
        assert res.status_code == 422 and res.json()["error"]["code"] == "E_INVALID", machine_id
    for machine_id in ("a" * 16, "A-z_0" * 25 + "abc"):
        body = {"machine_id": machine_id, "name": "Mac", "surface": "desktop", "mod_version": "1"}
        assert (await browser.http.post("/v1/device/code", json=body)).status_code == 200, machine_id
