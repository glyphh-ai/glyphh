"""The Glyphh connector, the way an MCP client and a browser use it: a client registered, the authorization code flow
with PKCE through the provider pages and the Allow page, tokens exchanged; or, for tests past signing in, a grant and
its tokens made straight in the database. And /mcp called as a 2026-07-28 client or an earlier one."""

import base64
import hashlib
import uuid
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import OAuthClient
from glyphh_server.ops.connector import grants, tokens
from tests.api.browser import went
from tests.conftest import PUBLIC_URL
from tests.db.helpers import Person

VERIFIER: str = "a-verifier-of-at-least-forty-three-characters-0123456789"
REDIRECT: str = "https://claude.ai/api/mcp/auth_callback"
RESOURCE: str = f"{PUBLIC_URL}/mcp"
MODERN: str = "2026-07-28"
UI: dict[str, Any] = {"extensions": {"io.modelcontextprotocol/ui": {"mimeTypes": ["text/html;profile=mcp-app"]}}}


def challenge(verifier: str = VERIFIER) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


async def register(http: httpx.AsyncClient, **over: Any) -> dict[str, Any]:
    body = {"client_name": "Claude", "redirect_uris": [REDIRECT], "token_endpoint_auth_method": "none", **over}
    res = await http.post("/oauth/register", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def ask(client: dict[str, Any], **over: Any) -> dict[str, Any]:
    params = {
        "response_type": "code",
        "client_id": client["client_id"],
        "redirect_uri": client["redirect_uris"][0],
        "state": "st-1",
        "code_challenge": challenge(),
        "code_challenge_method": "S256",
        "scope": "account",
        "resource": RESOURCE,
    }
    return {k: v for k, v in {**params, **over}.items() if v is not None}


async def to_allow(
    http: httpx.AsyncClient, params: dict[str, Any], provider: str = "google"
) -> tuple[dict[str, Any], str]:
    """The authorization request, the provider, and back: what the platform's Allow page shows (from /auth/consent)
    and the signed consent it was sent."""
    path, q = went(await http.get("/oauth/authorize", params=params))
    assert path == "/authorize" and q["client"], q
    started = await http.get(f"/auth/{provider}/start", params={"oauth": q["oauth"]})
    assert started.status_code == 302, started.text
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    back = await http.get(f"/auth/{provider}/callback", params={"code": "c-1", "state": state})
    path, q = went(back)
    assert path == "/allow", path
    shown = await http.get("/auth/consent", params={"consent": q["consent"]})
    assert shown.status_code == 200, shown.text
    return shown.json(), q["consent"]


async def allow(http: httpx.AsyncClient, consent: str, decision: str) -> httpx.Response:
    return await http.get("/auth/oauth/allow", params={"consent": consent, "decision": decision})


def query(res: httpx.Response) -> dict[str, str]:
    assert res.status_code == 302, res.text
    return {k: v[0] for k, v in parse_qs(urlsplit(res.headers["location"]).query).items()}


async def allowed_code(http: httpx.AsyncClient, client: dict[str, Any], **over: Any) -> str:
    _, consent = await to_allow(http, ask(client, **over))
    back = query(await allow(http, consent, "allow"))
    assert back["state"] == "st-1" and back["iss"] == PUBLIC_URL
    return back["code"]


async def exchange(http: httpx.AsyncClient, client: dict[str, Any], given: str, **over: Any) -> httpx.Response:
    form = {
        "grant_type": "authorization_code",
        "code": given,
        "redirect_uri": client["redirect_uris"][0],
        "client_id": client["client_id"],
        "code_verifier": VERIFIER,
        "resource": RESOURCE,
        **over,
    }
    return await http.post("/oauth/token", data={k: v for k, v in form.items() if v is not None})


async def connected(http: httpx.AsyncClient) -> tuple[dict[str, Any], dict[str, Any]]:
    """A client registered and allowed by the browser's person: the client, and its tokens."""
    client = await register(http)
    res = await exchange(http, client, await allowed_code(http, client))
    assert res.status_code == 200, res.text
    return client, res.json()


async def granted(engine: AsyncEngine, who: Person, resource: str = RESOURCE) -> tuple[uuid.UUID, dict[str, str]]:
    """A grant for a new client made straight in the database: its id, and /mcp's Authorization header."""
    async with engine.begin() as conn:
        values = {"name": "Claude", "redirect_uris": [REDIRECT], "auth_method": "none"}
        values |= {"grant_types": ["authorization_code", "refresh_token"]}
        client_id = (await conn.execute(insert(OAuthClient).values(values).returning(OAuthClient.id))).scalar_one()
        grant_id = await grants.grant_for(conn, who.user_id, client_id, "account", resource)
        answer = await tokens.issue(conn, grant_id, "account")
    return grant_id, {"authorization": f"Bearer {answer.access_token}"}


def modern(method: str, params: dict[str, Any] | None = None, caps: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = {"io.modelcontextprotocol/protocolVersion": MODERN, "io.modelcontextprotocol/clientCapabilities": caps or {}}
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": {**(params or {}), "_meta": meta}}


def modern_headers(body: dict[str, Any], auth: dict[str, str]) -> dict[str, str]:
    headers = {**auth, "mcp-protocol-version": MODERN, "mcp-method": body["method"]}
    named = body["params"].get("name") or body["params"].get("uri")
    return headers | ({"mcp-name": named} if named else {})


async def rpc(http: httpx.AsyncClient, auth: dict[str, str], method: str, **params: Any) -> dict[str, Any]:
    """A 2026-07-28 request, answered."""
    body = modern(method, params, UI)
    res = await http.post("/mcp", json=body, headers=modern_headers(body, auth))
    assert res.status_code == 200, res.text
    return res.json()


async def tool(http: httpx.AsyncClient, auth: dict[str, str], name: str, **arguments: Any) -> dict[str, Any]:
    """A tool's result."""
    return (await rpc(http, auth, "tools/call", name=name, arguments=arguments))["result"]
