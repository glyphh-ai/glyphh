"""The platform signs a person in for itself: no Allow, the refresh token in a cookie, the access token in hand."""

import base64
import hashlib
import secrets
from collections.abc import AsyncIterator
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import Membership, User
from glyphh_server.ops.auth import hosts
from tests.conftest import PLATFORM_URL, _client
from tests.db.helpers import make_org
from tests.fake_providers import PROVIDER_SETTINGS, provider_transport


@pytest.fixture
async def browser(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(create_app(PROVIDER_SETTINGS, http=httpx.AsyncClient(transport=provider_transport()))):
        yield c


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    return verifier, base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


async def _signed_in_code(browser: httpx.AsyncClient, challenge: str) -> str:
    params = {
        "response_type": "code",
        "client_id": "glyphh-platform",
        "redirect_uri": f"{PLATFORM_URL}/signed-in",
        "state": "p-1",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    link = urlsplit((await browser.get("/authorize", params=params)).headers["location"])
    token = parse_qs(link.query)["request"][0]
    started = await browser.get("/auth/google/start", params={"request": token})
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    back = await browser.get("/auth/google/callback", params={"code": "c-1", "state": state})
    assert back.status_code == 303 and back.headers["location"].startswith(f"{PLATFORM_URL}/signed-in?")
    return parse_qs(urlsplit(back.headers["location"]).query)["code"][0]


async def test_the_platform_signs_in_without_allow_and_keeps_its_session(
    browser: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    verifier, challenge = _pkce()
    code = await _signed_in_code(browser, challenge)
    started = await browser.post("/v1/session/token", json={"code": code, "verifier": verifier})
    assert started.status_code == 200 and "httponly" in started.headers["set-cookie"].lower()
    access = started.json()["access_token"]
    me = (await browser.get("/v1/me", headers={"authorization": f"Bearer {access}"})).json()
    assert me["email"] == "pages@google.test" and me["org"]["personal"] is True
    again = await browser.post("/v1/session/refresh")
    assert again.status_code == 200 and again.json()["access_token"] != access
    async with engine.connect() as conn:
        user = (await conn.execute(select(User.id).where(User.email == "pages@google.test"))).scalar_one()
        assert all(h.name != "Glyphh" for h in await hosts.connected(conn, user))
    assert (await browser.post("/v1/session/token", json={"code": code, "verifier": verifier})).json()["error"][
        "reason"
    ] == "invalid_code"


async def test_switching_org_and_signing_out(browser: httpx.AsyncClient, engine: AsyncEngine) -> None:
    verifier, challenge = _pkce()
    started = await browser.post(
        "/v1/session/token", json={"code": await _signed_in_code(browser, challenge), "verifier": verifier}
    )
    auth = {"authorization": f"Bearer {started.json()['access_token']}"}
    team, stranger = await make_org(engine, "Session Team Co"), await make_org(engine, "Session Stranger Co")
    async with engine.begin() as conn:
        user = (await conn.execute(select(User.id).where(User.email == "pages@google.test"))).scalar_one()
        await conn.execute(insert(Membership).values(user_id=user, org_id=team, role="user"))
    refused = await browser.post("/v1/session/switch", headers=auth, json={"org": str(stranger)})
    assert refused.status_code == 403 and refused.json()["error"]["reason"] == "not_a_member"
    moved = await browser.post("/v1/session/switch", headers=auth, json={"org": str(team)})
    there = {"authorization": f"Bearer {moved.json()['access_token']}"}
    assert (await browser.get("/v1/me", headers=there)).json()["org"]["name"] == "Session Team Co"
    assert (await browser.post("/v1/session/sign-out")).status_code == 204
    gone = await browser.post("/v1/session/refresh")
    assert gone.status_code == 401 and gone.json()["error"]["reason"] == "signed_out"


async def test_a_wrong_verifier_or_no_cookie_is_refused(browser: httpx.AsyncClient) -> None:
    _, challenge = _pkce()
    code = await _signed_in_code(browser, challenge)
    wrong = await browser.post("/v1/session/token", json={"code": code, "verifier": "not-the-verifier"})
    assert wrong.status_code == 422 and wrong.json()["error"]["reason"] == "invalid_code"
    browser.cookies.clear()
    assert (await browser.post("/v1/session/sign-out")).status_code == 204
    assert (await browser.post("/v1/session/refresh")).status_code == 401


async def test_switching_from_a_bare_token_and_a_code_raced_away(
    browser: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    from unittest.mock import AsyncMock, patch

    from glyphh_server.ops.auth import codes

    verifier, challenge = _pkce()
    started = await browser.post(
        "/v1/session/token", json={"code": await _signed_in_code(browser, challenge), "verifier": verifier}
    )
    browser.cookies.clear()
    async with engine.connect() as conn:
        personal = (
            (
                await conn.execute(
                    select(Membership.org_id)
                    .join(User, User.id == Membership.user_id)
                    .where(User.email == "pages@google.test")
                )
            )
            .scalars()
            .first()
        )
    auth = {"authorization": f"Bearer {started.json()['access_token']}"}
    assert (await browser.post("/v1/session/switch", headers=auth, json={"org": str(personal)})).status_code == 200
    verifier, challenge = _pkce()
    code = await _signed_in_code(browser, challenge)
    with patch.object(codes, "consume", AsyncMock(return_value=None)):
        raced = await browser.post("/v1/session/token", json={"code": code, "verifier": verifier})
    assert raced.json()["error"]["reason"] == "invalid_code"
