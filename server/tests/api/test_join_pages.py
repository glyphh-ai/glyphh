"""Joining an org from an invite link, the way a browser does it."""

from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import User
from glyphh_server.ops import invites
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
    page = await browser.get("/auth/join", params={"invite": token})
    assert page.status_code == 200 and "Join Join Co" in page.text
    started = await browser.get("/auth/google/start", params={"invite": token})
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    return await browser.get("/auth/google/callback", params={"code": "c", "state": state})


async def test_the_invited_person_signs_in_and_joins(browser: httpx.AsyncClient, engine: AsyncEngine) -> None:
    token = await _invite(engine, GOOGLE_ME["email"])
    joined = await _sign_in_from(browser, token)
    assert joined.status_code == 200 and "You've joined" in joined.text
    async with engine.connect() as conn:
        role = (await conn.execute(select(User.role).where(User.email == GOOGLE_ME["email"]))).scalar_one()
    assert role == "user"


async def test_signing_in_as_someone_else_is_refused(browser: httpx.AsyncClient, engine: AsyncEngine) -> None:
    token = await _invite(engine, "someone-else@join.test")
    refused = await _sign_in_from(browser, token)
    assert refused.status_code == 403 and "someone-else@join.test" in refused.text


async def test_a_dead_invite_link_gets_a_page_with_a_trace(browser: httpx.AsyncClient) -> None:
    for path in ("/auth/join?invite=nope", "/auth/google/start?invite=nope"):
        res = await browser.get(path)
        assert res.status_code == 422 and "trace" in res.text and "expired" in res.text
