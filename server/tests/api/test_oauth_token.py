"""The token endpoint: a code exchanged once with its PKCE verifier, refresh tokens rotated (one used twice revokes
the grant), the platform's client by its secret and no other client at all, revocation, and every refusal in OAuth's
own shape."""

import base64
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.api.gone import RETIRED
from glyphh_server.app import create_app
from glyphh_server.models import ConnectorToken, OAuthCode
from glyphh_server.ops.auth.secrets import hash_secret
from glyphh_server.ops.connector import grants, tokens
from tests.api.browser import Browser
from tests.conftest import PLATFORM_SECRET, PROVIDER_SETTINGS, _client
from tests.db.helpers import person
from tests.fakes import fake_http
from tests.oauth import CLIENT_ID, REDIRECT, RESOURCE, VERIFIER, allowed_code, basic, client_row, exchange

MINE: dict[str, str] = {"client_id": CLIENT_ID, "client_secret": PLATFORM_SECRET}
CLAUDE: str = "https://claude.ai/api/mcp/auth_callback"


def _error(res: httpx.Response, error: str, status: int = 400) -> None:
    assert (res.status_code, res.json()["error"]) == (status, error), res.text
    assert res.headers["cache-control"] == "no-store" and res.json()["error_description"]


def _gone(res: httpx.Response) -> None:
    assert res.status_code == 410, res.text
    assert res.json() == {
        "error": {"code": "E_WOUND_DOWN", "message": RETIRED, "trace_id": res.headers["x-request-id"]}
    }


async def _refresh(http: httpx.AsyncClient, token: str, **over: Any) -> httpx.Response:
    form = {"grant_type": "refresh_token", "refresh_token": token, **MINE, **over}
    return await http.post("/oauth/token", data={k: v for k, v in form.items() if v is not None})


async def _signed_in(http: httpx.AsyncClient) -> dict[str, Any]:
    """The browser's person signed in through the platform: its tokens."""
    res = await exchange(http, await allowed_code(http))
    assert res.status_code == 200, res.text
    return res.json()


async def _me(http: httpx.AsyncClient, access_token: str) -> httpx.Response:
    return await http.get("/v1/me", headers={"authorization": f"Bearer {access_token}"})


async def test_a_code_and_its_verifier_make_tokens_that_open_the_api_as_their_person(browser: Browser) -> None:
    res = await exchange(browser.http, await allowed_code(browser.http))
    assert res.status_code == 200 and res.headers["cache-control"] == "no-store"
    assert res.headers["pragma"] == "no-cache"
    answer = res.json()
    assert set(answer) == {"access_token", "token_type", "expires_in", "refresh_token", "scope"}
    assert (answer["token_type"], answer["expires_in"], answer["scope"]) == ("Bearer", 3600, "account")
    assert answer["access_token"] != answer["refresh_token"]
    me = await _me(browser.http, answer["access_token"])
    assert me.status_code == 200 and (me.json()["email"], me.json()["staff"]) == (browser.email, True)
    assert me.json()["providers"] == ["google"] and me.json()["role"] == "admin"


@pytest.mark.parametrize(
    "over",
    [
        {"code_verifier": "b" * 43},
        {"code_verifier": None},
        {"code_verifier": "short"},
        {"redirect_uri": "http://localhost:3000/other"},
        {"redirect_uri": None},
        {"code": "not-a-code"},
        {"code": None},
    ],
)
async def test_a_wrong_verifier_redirect_or_code_is_an_invalid_grant(browser: Browser, over: dict) -> None:
    code = await allowed_code(browser.http)
    _error(await exchange(browser.http, code, **over), "invalid_grant")


async def test_a_code_works_once_and_its_second_use_revokes_what_it_made(browser: Browser) -> None:
    code = await allowed_code(browser.http)
    first = (await exchange(browser.http, code)).json()
    assert (await _me(browser.http, first["access_token"])).status_code == 200
    _error(await exchange(browser.http, code), "invalid_grant")
    assert (await _me(browser.http, first["access_token"])).status_code == 401
    _error(await _refresh(browser.http, first["refresh_token"]), "invalid_grant")


async def test_an_expired_code_another_clients_code_or_another_resource_is_refused(
    browser: Browser, engine: AsyncEngine
) -> None:
    other = await client_row(engine, CLAUDE)
    theirs = await allowed_code(browser.http, client_id=other, redirect_uri=CLAUDE)
    _error(await exchange(browser.http, theirs, redirect_uri=CLAUDE), "invalid_grant")
    code = await allowed_code(browser.http)
    _error(await exchange(browser.http, code, resource="https://other.test/mcp"), "invalid_target")
    async with engine.begin() as conn:
        past = datetime.now(UTC) - timedelta(seconds=1)
        await conn.execute(update(OAuthCode).where(OAuthCode.code_hash == hash_secret(code)).values(expires_at=past))
    _error(await exchange(browser.http, code), "invalid_grant")


async def test_a_refresh_rotates_and_a_used_refresh_token_revokes_the_grant(
    browser: Browser, engine: AsyncEngine
) -> None:
    first = await _signed_in(browser.http)
    second = (await _refresh(browser.http, first["refresh_token"], scope="account", resource=RESOURCE)).json()
    assert second["refresh_token"] != first["refresh_token"] and second["access_token"] != first["access_token"]
    assert (await _me(browser.http, first["access_token"])).status_code == 200  # good for its hour
    assert (await _me(browser.http, second["access_token"])).status_code == 200
    _error(await _refresh(browser.http, first["refresh_token"]), "invalid_grant")
    _error(await _refresh(browser.http, second["refresh_token"]), "invalid_grant")
    async with engine.connect() as conn:
        held = select(ConnectorToken.revoked_at).where(ConnectorToken.token_hash == hash_secret(second["access_token"]))
        assert (await conn.execute(held)).scalar_one() is not None
    assert (await _me(browser.http, second["access_token"])).status_code == 401


async def test_a_refresh_cant_widen_scope_nor_use_an_access_token_an_expired_one_or_another_clients(
    browser: Browser, engine: AsyncEngine
) -> None:
    held = await _signed_in(browser.http)
    _error(await _refresh(browser.http, held["refresh_token"], scope="account admin"), "invalid_scope")
    _error(await _refresh(browser.http, held["access_token"]), "invalid_grant")
    _error(await _refresh(browser.http, "unknown"), "invalid_grant")
    _error(await _refresh(browser.http, None), "invalid_grant")
    _error(await _refresh(browser.http, held["refresh_token"], resource="https://x.test"), "invalid_target")
    ada, other = await person(engine), uuid.UUID(await client_row(engine, CLAUDE))
    async with engine.begin() as conn:  # a sign-in the retired connector left: another client's grant
        grant_id = await grants.grant_for(conn, ada.user_id, other, "account", RESOURCE)
        theirs = await tokens.issue(conn, grant_id, "account")
    _error(await _refresh(browser.http, theirs.refresh_token), "invalid_grant")
    async with engine.begin() as conn:
        mine = ConnectorToken.token_hash == hash_secret(held["refresh_token"])
        await conn.execute(update(ConnectorToken).where(mine).values(expires_at=datetime.now(UTC)))
    _error(await _refresh(browser.http, held["refresh_token"]), "invalid_grant")
    assert (await _me(browser.http, held["access_token"])).status_code == 200  # refused, but nothing revoked


async def test_an_unknown_grant_type_is_refused(browser: Browser) -> None:
    _error(await browser.http.post("/oauth/token", data=MINE), "unsupported_grant_type")
    _error(await browser.http.post("/oauth/token", data={**MINE, "grant_type": "password"}), "unsupported_grant_type")


async def test_a_grant_type_the_platforms_client_is_not_registered_for_is_refused(engine: AsyncEngine) -> None:
    only_codes = await client_row(engine, REDIRECT, ["authorization_code"])
    settings = PROVIDER_SETTINGS.model_copy(update={"platform_client_id": only_codes.upper()})
    async for http in _client(create_app(settings, http=fake_http())):
        form = {"grant_type": "refresh_token", "refresh_token": "x", "client_id": only_codes}
        _error(await http.post("/oauth/token", data=form), "unauthorized_client")
        _error(await http.post("/oauth/token", data=form | {"grant_type": "authorization_code"}), "invalid_grant")


async def test_the_platforms_client_authenticates_by_basic_or_post_and_a_wrong_secret_is_refused(
    browser: Browser,
) -> None:
    code = await allowed_code(browser.http)
    for over in ({"client_secret": "nope"}, {"client_secret": None}, {"client_id": None}, {"client_id": "nobody"}):
        refused = await exchange(browser.http, code, **over)
        _error(refused, "invalid_client", 401)
        assert "www-authenticate" not in refused.headers
    not_text = base64.b64encode(b"\xff\xfe:\xff").decode()
    for header in (basic(secret="nope")["authorization"], "Basic !!!not-base64", f"basic {not_text}"):
        res = await browser.http.post("/oauth/token", data={"grant_type": "x"}, headers={"authorization": header})
        _error(res, "invalid_client", 401)
        assert res.headers["www-authenticate"] == 'Basic realm="glyphh"'
    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "code_verifier": VERIFIER}
    ok = await browser.http.post("/oauth/token", data=form, headers=basic())
    assert ok.status_code == 200, ok.text
    by_post = await _refresh(browser.http, ok.json()["refresh_token"])
    assert by_post.status_code == 200
    encoded = basic(CLIENT_ID.replace("-", "%2D"), PLATFORM_SECRET.replace("-", "%2D"))  # each form-encoded
    form = {"grant_type": "refresh_token", "refresh_token": by_post.json()["refresh_token"]}
    assert (await browser.http.post("/oauth/token", data=form, headers=encoded)).status_code == 200


async def test_any_other_client_is_issued_nothing(browser: Browser, engine: AsyncEngine) -> None:
    other = await client_row(engine, CLAUDE)
    code = await allowed_code(browser.http, client_id=other, redirect_uri=CLAUDE)
    theirs = {"client_id": other, "client_secret": None, "redirect_uri": CLAUDE}
    _gone(await exchange(browser.http, code, **theirs))
    _gone(await _refresh(browser.http, "x", client_id=other, client_secret=None))
    _gone(await browser.http.post("/oauth/token", data={"client_id": other}))
    async with engine.connect() as conn:
        unused = select(OAuthCode.used_at).where(OAuthCode.code_hash == hash_secret(code))
        assert (await conn.execute(unused)).scalar_one() is None


async def test_revoking_a_refresh_token_ends_the_grant_and_an_access_token_only_itself(
    browser: Browser, engine: AsyncEngine
) -> None:
    first = await _signed_in(browser.http)
    res = await browser.http.post("/oauth/revoke", data={**MINE, "token": first["access_token"]})
    assert res.status_code == 200 and res.headers["cache-control"] == "no-store" and res.content == b""
    assert (await _me(browser.http, first["access_token"])).status_code == 401
    second = (await _refresh(browser.http, first["refresh_token"])).json()
    other = await client_row(engine, CLAUDE)
    for form in ({"client_id": other, "token": second["refresh_token"]}, {**MINE, "token": "unknown"}, MINE):
        assert (await browser.http.post("/oauth/revoke", data=form)).status_code == 200
        assert (await _me(browser.http, second["access_token"])).status_code == 200
    by_basic = await browser.http.post("/oauth/revoke", data={"token": second["refresh_token"]}, headers=basic())
    assert by_basic.status_code == 200
    assert (await _me(browser.http, second["access_token"])).status_code == 401
    _error(await _refresh(browser.http, second["refresh_token"]), "invalid_grant")
    _error(await browser.http.post("/oauth/revoke", data={"client_id": "nobody", "token": "x"}), "invalid_client", 401)
    wrong = await browser.http.post("/oauth/revoke", data={"token": "x"}, headers=basic(secret="nope"))
    _error(wrong, "invalid_client", 401)
    assert wrong.headers["www-authenticate"] == 'Basic realm="glyphh"'


async def test_signing_in_again_reuses_the_grant(browser: Browser, engine: AsyncEngine) -> None:
    first = await _signed_in(browser.http)
    again = await _signed_in(browser.http)
    async with engine.connect() as conn:
        found = select(ConnectorToken.grant_id).where(
            ConnectorToken.token_hash.in_([hash_secret(first["access_token"]), hash_secret(again["access_token"])])
        )
        assert len(set((await conn.execute(found)).scalars())) == 1
    assert (await _me(browser.http, first["access_token"])).status_code == 200
