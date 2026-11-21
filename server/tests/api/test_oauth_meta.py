"""Where an MCP client finds how to sign in: the protected resource's metadata (RFC 9728) at the root and after
/mcp, the authorization server's (RFC 8414), and the 401 that points at them."""

import httpx

from tests.conftest import PUBLIC_URL


async def test_the_protected_resource_names_the_connector_and_its_authorization_server(
    client: httpx.AsyncClient,
) -> None:
    for path in ("/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp"):
        res = await client.get(path)
        assert res.status_code == 200
        assert res.json() == {
            "resource": f"{PUBLIC_URL}/mcp",
            "authorization_servers": [PUBLIC_URL],
            "scopes_supported": ["account"],
            "bearer_methods_supported": ["header"],
            "resource_name": "Glyphh",
        }


async def test_the_authorization_server_requires_pkce_s256_and_says_it_sends_the_issuer(
    client: httpx.AsyncClient,
) -> None:
    meta = (await client.get("/.well-known/oauth-authorization-server")).json()
    assert meta["issuer"] == PUBLIC_URL
    assert (meta["authorization_endpoint"], meta["token_endpoint"]) == (
        f"{PUBLIC_URL}/oauth/authorize",
        f"{PUBLIC_URL}/oauth/token",
    )
    assert (meta["registration_endpoint"], meta["revocation_endpoint"]) == (
        f"{PUBLIC_URL}/oauth/register",
        f"{PUBLIC_URL}/oauth/revoke",
    )
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert meta["response_types_supported"] == ["code"]
    assert meta["grant_types_supported"] == ["authorization_code", "refresh_token"]
    assert meta["token_endpoint_auth_methods_supported"] == ["none", "client_secret_post", "client_secret_basic"]
    assert meta["scopes_supported"] == ["account"]
    assert meta["authorization_response_iss_parameter_supported"] is True


async def test_mcp_without_a_good_token_points_at_the_metadata(client: httpx.AsyncClient) -> None:
    hint = f'Bearer resource_metadata="{PUBLIC_URL}/.well-known/oauth-protected-resource/mcp", scope="account"'
    bare = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert bare.status_code == 401 and bare.headers["www-authenticate"] == hint
    assert bare.json()["error"]["code"] == "E_UNAUTHORIZED"
    for header in ("Bearer not-a-token", "Basic abc", "Bearer "):
        res = await client.post("/mcp", json={}, headers={"authorization": header})
        assert res.status_code == 401
        assert res.headers["www-authenticate"] == f'{hint}, error="invalid_token"'
