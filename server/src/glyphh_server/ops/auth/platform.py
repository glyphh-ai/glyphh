"""The platform's own sign-in: Glyphh's first-party client of its own OAuth. It signs in like an agent host
(PKCE, a one-time code) but needs no Allow, and keeps its refresh token in a cookie only the server reads."""

import base64
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Forbidden, Invalid
from glyphh_server.models import Membership, OAuthClient
from glyphh_server.ops.auth import codes, hosts, tokens
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.tokens import IssuedTokens

PLATFORM_CLIENT_ID: str = "glyphh-platform"
SIGNED_IN_PATH: str = "/signed-in"


async def seed_platform_client(conn: AsyncConnection, origins: list[str]) -> None:
    """Register the platform once, at every address it is opened at; re-registered on every boot so the
    addresses follow settings."""
    redirect = [f"{origin}{SIGNED_IN_PATH}" for origin in origins]
    await conn.execute(
        insert(OAuthClient)
        .values(client_id=PLATFORM_CLIENT_ID, name="Glyphh", redirect_uris=redirect)
        .on_conflict_do_update(index_elements=[OAuthClient.client_id], set_={"redirect_uris": redirect})
    )


def challenge_of(verifier: str) -> str:
    """PKCE S256: the challenge a verifier answers."""
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")


async def exchange(conn: AsyncConnection, code: str, verifier: str) -> IssuedTokens:
    """The platform's one-time code, and the verifier only it holds, for a pair of tokens acting in the code's org."""
    client = await hosts.find(conn, PLATFORM_CLIENT_ID)
    row = None if client is None else await codes.find(conn, client.id, code)
    if client is None or row is None or challenge_of(verifier) != row.code_challenge:
        raise Invalid("This sign-in didn't finish. Sign in again.", reason="invalid_code")
    who = await codes.consume(conn, code)
    if who is None:
        raise Invalid("This sign-in didn't finish. Sign in again.", reason="invalid_code")
    return await tokens.issue(conn, who[0], who[1], client.id)


async def switch(conn: AsyncConnection, who: Principal, org_id: uuid.UUID) -> IssuedTokens:
    """Act in another of my orgs: a new pair there, the old pair ended."""
    member = select(Membership.user_id).where(
        Membership.user_id == who.user_id, Membership.org_id == org_id, Membership.disabled_at.is_(None)
    )
    if (await conn.execute(member)).first() is None:
        raise Forbidden("You aren't in that org. Pick one of yours.", reason="not_a_member")
    return await tokens.issue(conn, who.user_id, org_id, who.oauth_client_id)
