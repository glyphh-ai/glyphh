"""The token endpoint: a code exchanged once with its PKCE verifier, refresh tokens rotated (one used twice revokes
the grant), confidential clients by their secret, revocation, and every refusal in OAuth's own shape."""

import base64
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import ConnectorToken, OAuthCode
from glyphh_server.ops.auth.secrets import hash_secret
from tests.api.browser import Browser, open_browser
from tests.connector import allowed_code, connected, exchange, register, rpc
from tests.fakes import FakeStripe


@pytest.fixture
async def browser(engine: AsyncEngine, stripe: FakeStripe) -> AsyncIterator[Browser]:
    async for b in open_browser(stripe):
        yield b


def _error(res: httpx.Response, error: str, status: int = 400) -> None:
    assert (res.status_code, res.json()["error"]) == (status, error), res.text
    assert res.headers["cache-control"] == "no-store" and res.json()["error_description"]


async def _refresh(http: httpx.AsyncClient, client: dict, token: str, **over: str) -> httpx.Response:
    form = {"grant_type": "refresh_token", "refresh_token": token, "client_id": client["client_id"], **over}
    return await http.post("/oauth/token", data=form)


async def test_a_code_and_its_verifier_make_tokens_that_open_mcp(browser: Browser) -> None:
    client = await register(browser.http)
    res = await exchange(browser.http, client, await allowed_code(browser.http, client))
    assert res.status_code == 200 and res.headers["cache-control"] == "no-store"
    tokens = res.json()
    assert (tokens["token_type"], tokens["expires_in"], tokens["scope"]) == ("Bearer", 3600, "account")
    assert tokens["access_token"] != tokens["refresh_token"]
    answer = await rpc(browser.http, {"authorization": f"Bearer {tokens['access_token']}"}, "ping")
    assert answer["result"]["resultType"] == "complete"


@pytest.mark.parametrize(
    "over",
    [
        {"code_verifier": "b" * 43},
        {"code_verifier": None},
        {"code_verifier": "short"},
        {"redirect_uri": "https://claude.ai/other"},
        {"code": "not-a-code"},
    ],
)
async def test_a_wrong_verifier_redirect_or_code_is_an_invalid_grant(browser: Browser, over: dict) -> None:
    client = await register(browser.http)
    code = await allowed_code(browser.http, client)
    _error(await exchange(browser.http, client, code, **over), "invalid_grant")


async def test_a_code_works_once_and_its_second_use_revokes_what_it_made(browser: Browser, engine: AsyncEngine) -> None:
    client = await register(browser.http)
    code = await allowed_code(browser.http, client)
    first = (await exchange(browser.http, client, code)).json()
    _error(await exchange(browser.http, client, code), "invalid_grant")
    assert (await _mcp(browser.http, first["access_token"])).status_code == 401
    _error(await _refresh(browser.http, client, first["refresh_token"]), "invalid_grant")


async def test_an_expired_code_another_clients_code_or_another_resource_is_refused(
    browser: Browser, engine: AsyncEngine
) -> None:
    client, other = await register(browser.http), await register(browser.http)
    code = await allowed_code(browser.http, client)
    _error(await exchange(browser.http, other, code, redirect_uri=client["redirect_uris"][0]), "invalid_grant")
    _error(await exchange(browser.http, client, code, resource="https://other.test/mcp"), "invalid_target")
    async with engine.begin() as conn:
        past = datetime.now(UTC) - timedelta(seconds=1)
        await conn.execute(update(OAuthCode).where(OAuthCode.code_hash == hash_secret(code)).values(expires_at=past))
    _error(await exchange(browser.http, client, code), "invalid_grant")


async def test_a_refresh_rotates_and_a_used_refresh_token_revokes_the_grant(
    browser: Browser, engine: AsyncEngine
) -> None:
    client, first = await connected(browser.http)
    second = (await _refresh(browser.http, client, first["refresh_token"], scope="account")).json()
    assert second["refresh_token"] != first["refresh_token"] and second["access_token"] != first["access_token"]
    assert (await rpc(browser.http, {"authorization": f"Bearer {first['access_token']}"}, "ping"))["result"] == {
        "resultType": "complete",
        "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "glyphh", "title": "Glyphh", "version": "test"}},
    }
    _error(await _refresh(browser.http, client, first["refresh_token"]), "invalid_grant")
    _error(await _refresh(browser.http, client, second["refresh_token"]), "invalid_grant")
    async with engine.connect() as conn:
        held = select(ConnectorToken.revoked_at).where(ConnectorToken.token_hash == hash_secret(second["access_token"]))
        assert (await conn.execute(held)).scalar_one() is not None


async def test_a_refresh_cant_widen_scope_nor_use_an_access_token_an_expired_one_or_another_clients(
    browser: Browser, engine: AsyncEngine
) -> None:
    client, tokens = await connected(browser.http)
    other = await register(browser.http)
    _error(await _refresh(browser.http, client, tokens["refresh_token"], scope="account admin"), "invalid_scope")
    _error(await _refresh(browser.http, client, tokens["access_token"]), "invalid_grant")
    _error(await _refresh(browser.http, other, tokens["refresh_token"]), "invalid_grant")
    _error(await _refresh(browser.http, client, tokens["refresh_token"], resource="https://x.test"), "invalid_target")
    async with engine.begin() as conn:
        mine = ConnectorToken.token_hash == hash_secret(tokens["refresh_token"])
        await conn.execute(update(ConnectorToken).where(mine).values(expires_at=datetime.now(UTC)))
    _error(await _refresh(browser.http, client, tokens["refresh_token"]), "invalid_grant")


async def test_an_unknown_grant_type_or_one_the_client_didnt_register_for_is_refused(browser: Browser) -> None:
    client = await register(browser.http, grant_types=["authorization_code"])
    _error(await browser.http.post("/oauth/token", data={"client_id": client["client_id"]}), "unsupported_grant_type")
    _error(await _refresh(browser.http, client, "x"), "unauthorized_client")
    form = {"grant_type": "password", "client_id": client["client_id"]}
    _error(await browser.http.post("/oauth/token", data=form), "unsupported_grant_type")


async def test_a_confidential_client_authenticates_by_basic_or_post_and_a_wrong_secret_is_refused(
    browser: Browser,
) -> None:
    client = await register(browser.http, token_endpoint_auth_method="client_secret_basic")
    code = await allowed_code(browser.http, client)
    basic = base64.b64encode(f"{client['client_id']}:{client['client_secret']}".encode()).decode()
    wrong = base64.b64encode(f"{client['client_id']}:nope".encode()).decode()
    refused = await exchange(browser.http, client, code, client_id=None, client_secret="nope")
    _error(refused, "invalid_client", 401)
    assert "www-authenticate" not in refused.headers
    for header in (f"Basic {wrong}", "Basic !!!not-base64"):
        res = await browser.http.post("/oauth/token", data={"grant_type": "x"}, headers={"authorization": header})
        _error(res, "invalid_client", 401)
        assert res.headers["www-authenticate"] == 'Basic realm="glyphh"'
    form = {"grant_type": "authorization_code", "code": code, "redirect_uri": client["redirect_uris"][0]}
    form["code_verifier"] = "a-verifier-of-at-least-forty-three-characters-0123456789"
    ok = await browser.http.post("/oauth/token", data=form, headers={"authorization": f"Basic {basic}"})
    assert ok.status_code == 200, ok.text
    by_post = await _refresh(browser.http, client, ok.json()["refresh_token"], client_secret=client["client_secret"])
    assert by_post.status_code == 200


async def test_revoking_a_refresh_token_ends_the_grant_and_an_access_token_only_itself(browser: Browser) -> None:
    client, first = await connected(browser.http)
    other = await register(browser.http)
    mine = {"client_id": client["client_id"]}
    res = await browser.http.post("/oauth/revoke", data={**mine, "token": first["access_token"]})
    assert res.status_code == 200 and res.headers["cache-control"] == "no-store"
    assert (await _mcp(browser.http, first["access_token"])).status_code == 401
    second = (await _refresh(browser.http, client, first["refresh_token"])).json()
    await browser.http.post("/oauth/revoke", data={"client_id": other["client_id"], "token": second["refresh_token"]})
    await browser.http.post("/oauth/revoke", data={**mine, "token": "unknown"})
    assert (await _mcp(browser.http, second["access_token"])).status_code == 200
    await browser.http.post("/oauth/revoke", data={**mine, "token": second["refresh_token"]})
    assert (await _mcp(browser.http, second["access_token"])).status_code == 401
    _error(await _refresh(browser.http, client, second["refresh_token"]), "invalid_grant")
    _error(await browser.http.post("/oauth/revoke", data={"client_id": "nobody", "token": "x"}), "invalid_client", 401)


async def _mcp(http: httpx.AsyncClient, access_token: str) -> httpx.Response:
    body = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    return await http.post("/mcp", json=body, headers={"authorization": f"Bearer {access_token}"})


async def test_allowing_the_same_client_again_reuses_its_grant(browser: Browser, engine: AsyncEngine) -> None:
    client, first = await connected(browser.http)
    again = (await exchange(browser.http, client, await allowed_code(browser.http, client))).json()
    async with engine.connect() as conn:
        found = select(ConnectorToken.grant_id).where(
            ConnectorToken.token_hash.in_([hash_secret(first["access_token"]), hash_secret(again["access_token"])])
        )
        assert len(set((await conn.execute(found)).scalars())) == 1
    assert (await _mcp(browser.http, first["access_token"])).status_code == 200
