"""Checking an authorization request (OAuth 2.1 section 4.1.1, with PKCE S256 and RFC 8707's resource). An unknown
client or redirect URI is refused on the page itself (Invalid); anything else wrong goes back to the redirect URI."""

import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.errors import Invalid
from glyphh_server.models import Rrotor
from glyphh_server.ops.connector import clients
from glyphh_server.ops.connector.errors import AuthorizeRefused

SCOPE: str = "account"
PKCE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
MACHINE: re.Pattern[str] = re.compile(r"^[0-9a-z]{6,32}$")
NOT_OURS: str = "Glyphh issues tokens for its own connector and for a runtime: hosted, or self-hosted and registered."


@dataclass(frozen=True, slots=True)
class AuthorizeRequest:
    client_id: str
    client_name: str
    redirect_uri: str
    state: str
    challenge: str
    scope: str
    resource: str

    def signed(self) -> dict[str, Any]:
        return asdict(self)


def canonical(uri: str) -> str:
    """A URI with its scheme and host lowercased and no trailing slash, to compare resources."""
    parts = urlsplit(uri.strip())
    path = parts.path.rstrip("/")
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}" + (f"?{parts.query}" if parts.query else "")


def runtime_host(asked: str) -> str | None:
    """The host of an address asked for as a runtime: `https://<host>`, with or without `/mcp`, and nothing else."""
    parts = urlsplit(asked.strip())
    if parts.scheme.lower() != "https" or parts.path.rstrip("/") not in ("", "/mcp") or parts.query or parts.fragment:
        return None
    return parts.netloc.lower() or None


def is_hosted(settings: Settings, host: str) -> bool:
    """`<machine>.<domain>`: a hosted runtime's address. The machine need not exist yet; the runtime that
    introspects the token is the one that says whether it is its own."""
    label, dot, rest = host.partition(".")
    return bool(dot) and rest == settings.fly_public_domain.lower() and MACHINE.match(label) is not None


async def runtime_resource(conn: AsyncConnection, settings: Settings, asked: str) -> str | None:
    """A runtime's address as a resource, hosted or a registered self-hosted one's: the token is bound to its
    `/mcp`. Looked up before anyone is known, so across every org."""
    host = runtime_host(asked)
    if host is None:
        return None
    address = f"https://{host}"
    if not is_hosted(settings, host):
        registered = select(Rrotor.id).where(Rrotor.mode == "self", Rrotor.public_url == address).limit(1)
        if (await conn.execute(registered)).first() is None:
            return None
    return f"{address}/mcp"


async def resource_for(conn: AsyncConnection, settings: Settings, asked: str | None) -> str:
    """The resource a token will be bound to: the connector, named as itself or as the server, or a runtime's
    address."""
    if asked is None or canonical(asked) in (canonical(settings.mcp_resource), canonical(settings.base_url)):
        return settings.mcp_resource
    runtime = await runtime_resource(conn, settings, asked)
    if runtime is not None:
        return runtime
    raise AuthorizeRefused("invalid_target", NOT_OURS)


def scope_for(asked: str | None) -> str:
    scopes = set((asked or SCOPE).split())
    if not scopes <= {SCOPE}:
        raise AuthorizeRefused("invalid_scope", f"The only scope is {SCOPE}.")
    return SCOPE


async def known_client(conn: AsyncConnection, client_id: str | None, redirect_uri: str | None) -> Any:
    client = await clients.find(conn, client_id)
    if client is None:
        raise Invalid("This app isn't registered with Glyphh. Start again from the app.", reason="unknown_client")
    if redirect_uri not in client.redirect_uris:
        raise Invalid("This app's return address isn't the one it registered.", reason="redirect_uri")
    return client


def check_rest(client: Any, q: dict[str, str]) -> None:
    if q.get("response_type") != "code":
        raise AuthorizeRefused("unsupported_response_type", "Only response_type=code is supported.")
    if "authorization_code" not in client.grant_types:
        raise AuthorizeRefused("unauthorized_client", "This client didn't register for authorization codes.")
    if not q.get("state"):
        raise AuthorizeRefused("invalid_request", "state is required.")
    if q.get("code_challenge_method") != "S256" or not PKCE.match(q.get("code_challenge", "")):
        raise AuthorizeRefused("invalid_request", "PKCE is required: code_challenge with code_challenge_method=S256.")


async def check(conn: AsyncConnection, settings: Settings, q: dict[str, str]) -> AuthorizeRequest:
    client = await known_client(conn, q.get("client_id"), q.get("redirect_uri"))
    check_rest(client, q)
    return AuthorizeRequest(
        client_id=str(client.id),
        client_name=client.name,
        redirect_uri=q["redirect_uri"],
        state=q["state"],
        challenge=q["code_challenge"],
        scope=scope_for(q.get("scope")),
        resource=await resource_for(conn, settings, q.get("resource")),
    )
