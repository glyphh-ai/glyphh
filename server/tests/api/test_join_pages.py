"""Joining an org from an invite, the way a browser does it: the platform's screen, then the server's steps."""

from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import User
from glyphh_server.ops import invites
from tests.api.test_sign_in_pages import screen
from tests.conftest import _client
from tests.db.helpers import admin_of
from tests.fake_providers import GOOGLE_ME, PROVIDER_SETTINGS, provider_transport


@pytest.fixture
async def browser(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(create_app(PROVIDER_SETTINGS, http=httpx.AsyncClient(transport=provider_transport()))):
        yield c


async def _invite(engine: AsyncEngine, email: str) -> str:
    boss = await admin_of(engine, f"Join Co {email}")
    async with engine.begin() as conn:
        return (await invites.create_invite(conn, boss, email, "user"))[1]


async def _sign_in_from(browser: httpx.AsyncClient, token: str) -> httpx.Response:
    shown = (await browser.get("/v1/auth/join", params={"invite": token})).json()
    assert shown["org"].startswith("Join Co") and shown["role"] == "user" and shown["providers"] == ["google", "github"]
    started = await browser.get("/auth/google/start", params={"invite": token})
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    return await browser.get("/auth/google/callback", params={"code": "c", "state": state})


async def test_the_invited_person_signs_in_and_joins(browser: httpx.AsyncClient, engine: AsyncEngine) -> None:
    token = await _invite(engine, GOOGLE_ME["email"])
    joined = screen(await _sign_in_from(browser, token), "/joined")
    assert joined["org"].startswith("Join Co")
    async with engine.connect() as conn:
        role = (await conn.execute(select(User.role).where(User.email == GOOGLE_ME["email"]))).scalar_one()
    assert role == "user"


async def test_signing_in_as_someone_else_is_refused(browser: httpx.AsyncClient, engine: AsyncEngine) -> None:
    token = await _invite(engine, "someone-else@join.test")
    problem = screen(await _sign_in_from(browser, token), "/problem")
    assert problem["code"] == "E_FORBIDDEN" and "someone-else@join.test" in problem["message"]
    assert (problem["reason"], problem["invited"], problem["email"]) == (
        "wrong_account",
        "someone-else@join.test",
        GOOGLE_ME["email"],
    )


async def test_a_dead_invite_is_refused_on_the_screen_and_the_step(browser: httpx.AsyncClient) -> None:
    shown = await browser.get("/v1/auth/join", params={"invite": "nope"})
    assert shown.status_code == 422 and "expired" in shown.json()["error"]["message"]
    problem = screen(await browser.get("/auth/google/start", params={"invite": "nope"}), "/problem")
    assert problem["code"] == "E_INVALID" and "expired" in problem["message"] and problem["reason"] == "expired"
