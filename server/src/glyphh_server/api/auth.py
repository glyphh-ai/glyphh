"""Who is calling the API: the grant behind an OAuth access token (the platform signs in as an OAuth client), or a
refusal. Anything wrong with the header or the token is one answer, E_UNAUTHORIZED, so nothing is learned by probing
it. A good token's request then sees only its own org's rows (db/tenancy.py)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.api.gone import staff_only
from glyphh_server.config import Settings
from glyphh_server.db import tenancy
from glyphh_server.errors import Forbidden, Unauthorized
from glyphh_server.obs import context
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.connector import tokens

SUSPENDED: str = "This organisation is suspended. Contact support@glyphh.ai."

bearer = HTTPBearer(auto_error=False, description="An OAuth access token, from the platform's sign-in")


async def connection(request: Request) -> AsyncIterator[AsyncConnection]:
    """One transaction per request: committed when the route returns, rolled back when it raises."""
    engine: AsyncEngine = request.app.state.engine
    async with engine.begin() as conn:
        yield conn


Conn = Annotated[AsyncConnection, Depends(connection)]
Bearer = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


async def authenticate(conn: AsyncConnection, creds: HTTPAuthorizationCredentials | None, resource: str) -> Principal:
    """The caller behind the token; from here to the end of the transaction, conn sees only the caller's org."""
    who = None if creds is None else await tokens.principal_for(conn, creds.credentials, resource)
    if who is None:
        raise Unauthorized("Sign in to Glyphh again: this token is not valid.")
    if who.suspended:
        raise Forbidden(SUSPENDED, reason="suspended")
    context.user_id.set(str(who.user_id))
    context.org_id.set(str(who.org_id))
    await tenancy.enter(conn, who.org_id)
    return who


async def principal(request: Request, conn: Conn, creds: Bearer) -> Principal:
    settings: Settings = request.app.state.settings
    who = await authenticate(conn, creds, settings.token_resource)
    staff_only(settings, who.email)  # a token that is not staff's is no good any more
    return who


Caller = Annotated[Principal, Depends(principal)]
