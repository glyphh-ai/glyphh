"""Registering an MCP client (RFC 7591): public or confidential, its redirect URIs https or on this machine, and every
refusal in OAuth's own shape."""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import OAuthClient
from glyphh_server.ops.auth.secrets import hash_secret
from tests.connector import REDIRECT, register


async def test_a_public_client_registers_without_a_secret(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    made = await register(client, scope="account", logo_uri="https://claude.ai/logo.png")
    assert made["client_name"] == "Claude" and made["redirect_uris"] == [REDIRECT]
    assert (made["token_endpoint_auth_method"], made["response_types"]) == ("none", ["code"])
    assert made["grant_types"] == ["authorization_code", "refresh_token"]
    assert "client_secret" not in made and made["client_id_issued_at"] > 0
    async with engine.connect() as conn:
        row = (await conn.execute(select(OAuthClient).where(OAuthClient.id == made["client_id"]))).one()
    assert (row.auth_method, row.secret_hash) == ("none", None)


async def test_a_confidential_client_gets_its_secret_once_kept_as_a_hash(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    res = await client.post("/oauth/register", json={"redirect_uris": ["http://127.0.0.1:33418/cb"]})
    made = res.json()
    assert res.headers["cache-control"] == "no-store"
    assert (made["token_endpoint_auth_method"], made["client_secret_expires_at"]) == ("client_secret_basic", 0)
    assert made["client_name"] == "127.0.0.1" and made["grant_types"] == ["authorization_code", "refresh_token"]
    async with engine.connect() as conn:
        found = select(OAuthClient.secret_hash).where(OAuthClient.id == made["client_id"])
        assert (await conn.execute(found)).scalar_one() == hash_secret(made["client_secret"])


@pytest.mark.parametrize(
    "uri", ["http://claude.ai/cb", "https://claude.ai/cb#frag", "ftp://x.test/cb", "https:///nohost", "x" * 10]
)
async def test_a_redirect_uri_not_https_nor_on_this_machine_is_refused(client: httpx.AsyncClient, uri: str) -> None:
    res = await client.post("/oauth/register", json={"redirect_uris": [uri]})
    assert res.status_code == 400 and res.json()["error"] == "invalid_redirect_uri"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"redirect_uris": []},
        {"redirect_uris": [REDIRECT] * 11},
        {"redirect_uris": [REDIRECT], "token_endpoint_auth_method": "private_key_jwt"},
        {"redirect_uris": [REDIRECT], "grant_types": ["client_credentials"]},
        {"redirect_uris": [REDIRECT], "response_types": ["token"]},
        {"redirect_uris": [REDIRECT], "client_name": "x" * 101},
        ["not", "an", "object"],
    ],
)
async def test_metadata_out_of_bounds_is_refused(client: httpx.AsyncClient, body: object) -> None:
    res = await client.post("/oauth/register", json=body)
    assert res.status_code == 400 and res.json()["error"] == "invalid_client_metadata"
    assert res.json()["error_description"]


async def test_a_body_that_isnt_json_is_refused(client: httpx.AsyncClient) -> None:
    res = await client.post("/oauth/register", content=b"redirect_uris=x", headers={"content-type": "text/plain"})
    assert res.status_code == 400 and res.json()["error"] == "invalid_client_metadata"


async def test_localhost_and_ipv6_loopback_are_allowed_over_http(client: httpx.AsyncClient) -> None:
    made = await register(client, redirect_uris=["http://localhost:6274/cb", "http://[::1]:8080/cb"], client_name="  ")
    assert made["client_name"] == "localhost"
