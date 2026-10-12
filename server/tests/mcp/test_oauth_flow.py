"""The whole sign-in, the way Claude Code or Codex runs it: register, authorize, the member signs in and
allows, trade the code (with PKCE) for tokens, call a tool, refresh, revoke."""

import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.auth import codes
from tests.conftest import SECRET_KEY
from tests.db.helpers import make_org, make_user
from tests.test_health import MCP_HEADERS, _sse_result

REDIRECT: str = "http://localhost:33418/callback"


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


async def _register(client: httpx.AsyncClient, **extra: object) -> dict:
    res = await client.post("/register", json={"redirect_uris": [REDIRECT], "client_name": "Claude Code", **extra})
    assert res.status_code == 201, res.text
    return res.json()


async def _authorize(client: httpx.AsyncClient, client_id: str, challenge: str) -> str:
    res = await client.get(
        "/authorize",
        params={
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "state": "st-1",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
    )
    assert res.status_code == 302, res.text
    return res.headers["location"]


async def _member_allows(engine: AsyncEngine, sign_in_link: str, email: str) -> str:
    pending = codes.read_pending(SECRET_KEY, parse_qs(urlsplit(sign_in_link).query)["request"][0])
    org = await make_org(engine, f"Org of {email}")
    user = await make_user(engine, org, email, "org_admin")
    async with engine.begin() as conn:
        back = await codes.approve(conn, pending, user, org)
    query = parse_qs(urlsplit(back).query)
    assert query["state"] == ["st-1"]
    return query["code"][0]


async def _token(client: httpx.AsyncClient, **form: str) -> httpx.Response:
    return await client.post("/token", data=form)


async def _me(client: httpx.AsyncClient, access: str) -> httpx.Response:
    return await client.post(
        "/mcp",
        headers={**MCP_HEADERS, "authorization": f"Bearer {access}"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "me", "arguments": {}}},
    )


async def test_a_host_signs_a_member_in_end_to_end(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    host = await _register(client, token_endpoint_auth_method="none")
    assert host["token_endpoint_auth_method"] == "none" and not host.get("client_secret")
    verifier, challenge = _pkce()
    link = await _authorize(client, host["client_id"], challenge)
    assert link.startswith("http://platform.test/sign-in?request=")
    code = await _member_allows(engine, link, "flow@oauth.test")

    wrong = await _token(
        client,
        grant_type="authorization_code",
        code=code,
        redirect_uri=REDIRECT,
        client_id=host["client_id"],
        code_verifier="x" * 50,
    )
    assert wrong.status_code == 400 and wrong.json()["error"] == "invalid_grant"
    res = await _token(
        client,
        grant_type="authorization_code",
        code=code,
        redirect_uri=REDIRECT,
        client_id=host["client_id"],
        code_verifier=verifier,
    )
    assert res.status_code == 200, res.text
    issued = res.json()
    again = await _token(
        client,
        grant_type="authorization_code",
        code=code,
        redirect_uri=REDIRECT,
        client_id=host["client_id"],
        code_verifier=verifier,
    )
    assert again.status_code == 400 and again.json()["error"] == "invalid_grant"

    me = _sse_result((await _me(client, issued["access_token"])).text)["result"]
    assert me["structuredContent"]["email"] == "flow@oauth.test" and not me.get("isError")

    fresh = (
        await _token(
            client, grant_type="refresh_token", refresh_token=issued["refresh_token"], client_id=host["client_id"]
        )
    ).json()
    assert (await _me(client, issued["access_token"])).status_code == 401
    stale = await _token(
        client, grant_type="refresh_token", refresh_token=issued["refresh_token"], client_id=host["client_id"]
    )
    assert stale.status_code == 400

    # The SDK's revocation form requires a client_secret field even from a public client: sent empty.
    revoked = await client.post(
        "/revoke", data={"token": fresh["access_token"], "client_id": host["client_id"], "client_secret": ""}
    )
    assert revoked.status_code == 200, revoked.text
    assert (await _me(client, fresh["access_token"])).status_code == 401


async def test_a_host_that_asks_for_a_secret_is_registered_public(client: httpx.AsyncClient) -> None:
    host = await _register(client)
    assert host["token_endpoint_auth_method"] == "none" and not host.get("client_secret")


async def test_mcp_without_a_token_points_the_host_at_sign_in(client: httpx.AsyncClient) -> None:
    res = await client.post("/mcp", headers=MCP_HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert res.status_code == 401
    assert "/.well-known/oauth-protected-resource" in res.headers["www-authenticate"]


async def test_the_server_publishes_its_oauth_metadata(client: httpx.AsyncClient) -> None:
    server = (await client.get("/.well-known/oauth-authorization-server")).json()
    assert server["issuer"].rstrip("/") == "http://localhost:8080"
    assert (
        server["registration_endpoint"].endswith("/register") and "S256" in server["code_challenge_methods_supported"]
    )
    resource = (await client.get("/.well-known/oauth-protected-resource/mcp")).json()
    assert resource["resource"] == "http://localhost:8080/mcp"
