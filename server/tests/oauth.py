"""The platform's sign-in, the way the platform and a browser do it: the authorization code flow with PKCE through
the provider pages and the Allow page, then the code exchanged at the token endpoint. There is one client, the
platform's own, made by the schema step (db/seed_clients.py); a test of any other gives its id and return address."""

import base64
import hashlib
from collections.abc import Sequence
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import OAuthClient
from glyphh_server.ops.connector.clients import GRANT_TYPES
from tests.api.browser import went
from tests.conftest import PLATFORM_ID, PLATFORM_SECRET, PUBLIC_URL

VERIFIER: str = "a-verifier-of-at-least-forty-three-characters-0123456789"
REDIRECT: str = "http://localhost:3000/auth/callback"
RESOURCE: str = f"{PUBLIC_URL}/mcp"
CLIENT_ID: str = str(PLATFORM_ID)


def challenge(verifier: str = VERIFIER) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


def basic(client_id: str = CLIENT_ID, secret: str = PLATFORM_SECRET) -> dict[str, str]:
    """The client's HTTP Basic header."""
    return {"authorization": "Basic " + base64.b64encode(f"{client_id}:{secret}".encode()).decode()}


async def client_row(
    engine: AsyncEngine, redirect_uri: str = REDIRECT, grant_types: Sequence[str] = GRANT_TYPES
) -> str:
    """A public OAuth client that is not the platform's, as the retired connector left them in the database: its id."""
    values = {"name": "Claude", "redirect_uris": [redirect_uri], "auth_method": "none"}
    async with engine.begin() as conn:
        made = insert(OAuthClient).values(**values, grant_types=list(grant_types)).returning(OAuthClient.id)
        return str((await conn.execute(made)).scalar_one())


def ask(**over: Any) -> dict[str, Any]:
    """The platform's authorization request; a None leaves the parameter out."""
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT,
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
    assert started.status_code == 302 and "glyphh_signin" in started.headers["set-cookie"], started.text
    state = parse_qs(urlsplit(started.headers["location"]).query)["state"][0]
    back = await http.get(f"/auth/{provider}/callback", params={"code": "c-1", "state": state})
    path, q = went(back)
    assert path == "/allow", (path, q)
    shown = await http.get("/auth/consent", params={"consent": q["consent"]})
    assert shown.status_code == 200, shown.text
    return shown.json(), q["consent"]


async def allow(http: httpx.AsyncClient, consent: str, decision: str) -> httpx.Response:
    return await http.get("/auth/oauth/allow", params={"consent": consent, "decision": decision})


def query(res: httpx.Response) -> dict[str, str]:
    """A redirect back to the client: its query values."""
    assert res.status_code == 302, res.text
    return {k: v[0] for k, v in parse_qs(urlsplit(res.headers["location"]).query).items()}


async def allowed_code(http: httpx.AsyncClient, **over: Any) -> str:
    """An authorization code, allowed by the browser's person."""
    _, consent = await to_allow(http, ask(**over))
    back = query(await allow(http, consent, "allow"))
    assert back["state"] == "st-1" and back["iss"] == PUBLIC_URL
    return back["code"]


async def exchange(http: httpx.AsyncClient, given: str, **over: Any) -> httpx.Response:
    """The code for tokens, the client authenticating in the form; a None leaves the field out."""
    form = {
        "grant_type": "authorization_code",
        "code": given,
        "redirect_uri": REDIRECT,
        "client_id": CLIENT_ID,
        "client_secret": PLATFORM_SECRET,
        "code_verifier": VERIFIER,
        "resource": RESOURCE,
        **over,
    }
    return await http.post("/oauth/token", data={k: v for k, v in form.items() if v is not None})
