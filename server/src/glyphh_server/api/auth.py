"""Who is calling the API: the install behind the bearer token, or a refusal. Anything wrong with the header or the
token is one answer, E_UNAUTHORIZED, so nothing is learned by probing it. A good token's request then sees only its
own org's rows (db/tenancy.py)."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Unauthorized
from glyphh_server.obs import context
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.tokens import principal_for

bearer = HTTPBearer(auto_error=False, description="The install's token, from the device flow")


async def connection(request: Request) -> AsyncIterator[AsyncConnection]:
    """One transaction per request: committed when the route returns, rolled back when it raises."""
    engine: AsyncEngine = request.app.state.engine
    async with engine.begin() as conn:
        yield conn


Conn = Annotated[AsyncConnection, Depends(connection)]


Bearer = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


async def authenticate(conn: AsyncConnection, creds: HTTPAuthorizationCredentials | None) -> Principal:
    """The caller behind the token; from here to the end of the transaction, conn sees only the caller's org."""
    if creds is None:
        raise Unauthorized("Sign in to Glyphh: send your install's token as a Bearer token.")
    who = await principal_for(conn, creds.credentials)
    context.user_id.set(str(who.user_id))
    context.org_id.set(str(who.org_id))
    await tenancy.enter(conn, who.org_id)
    return who


async def principal(conn: Conn, creds: Bearer) -> Principal:
    return await authenticate(conn, creds)


Caller = Annotated[Principal, Depends(principal)]
