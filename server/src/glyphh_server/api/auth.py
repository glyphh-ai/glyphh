"""Who is calling the API: the install behind the bearer token, or the OAuth grant behind an access token (the
platform signs in as an OAuth client), or a refusal. Anything wrong with the header or the
token is one answer, E_UNAUTHORIZED, so nothing is learned by probing it. A good token's request then sees only its
own org's rows (db/tenancy.py)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.api.wound_down import staff_only
from glyphh_server.config import Settings
from glyphh_server.db import tenancy
from glyphh_server.errors import Forbidden, Unauthorized
from glyphh_server.obs import context
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.tokens import principal_for
from glyphh_server.ops.connector import tokens as connector_tokens

SUSPENDED: str = "This organisation is suspended. Contact support@glyphh.ai."

bearer = HTTPBearer(auto_error=False, description="The install's token from the device flow, or an OAuth access token")


async def connection(request: Request) -> AsyncIterator[AsyncConnection]:
    """One transaction per request: committed when the route returns, rolled back when it raises."""
    engine: AsyncEngine = request.app.state.engine
    async with engine.begin() as conn:
        yield conn


Conn = Annotated[AsyncConnection, Depends(connection)]


def settings_of(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


Cfg = Annotated[Settings, Depends(settings_of)]


Bearer = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


async def authenticate(conn: AsyncConnection, creds: HTTPAuthorizationCredentials | None, resource: str) -> Principal:
    """The caller behind the token; from here to the end of the transaction, conn sees only the caller's org.
    An install's token is tried first, then an OAuth access token bound to `resource`; anything else is the
    install lookup's own refusal, so the answer is the same whichever kind was sent."""
    if creds is None:
        raise Unauthorized("Sign in to Glyphh: send your install's token as a Bearer token.")
    try:
        who = await principal_for(conn, creds.credentials)
    except Unauthorized:
        granted = await connector_tokens.principal_for(conn, creds.credentials, resource)
        if granted is None:
            raise
        who = granted
    if who.suspended:
        raise Forbidden(SUSPENDED, reason="suspended")
    context.user_id.set(str(who.user_id))
    context.org_id.set(str(who.org_id))
    await tenancy.enter(conn, who.org_id)
    return who


async def principal(request: Request, conn: Conn, creds: Bearer) -> Principal:
    settings: Settings = request.app.state.settings
    who = await authenticate(conn, creds, settings.mcp_resource)
    staff_only(settings, who.email)  # wound down, a token that is not staff's is no good any more
    return who


Caller = Annotated[Principal, Depends(principal)]
