"""Who is calling the API: the member behind the bearer token, or a refusal. Anything wrong with the
header or the token is one answer, E_UNAUTHORIZED, so nothing is learned by probing it."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.errors import Unauthorized
from glyphh_server.obs import context
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.tokens import principal_for


async def connection(request: Request) -> AsyncIterator[AsyncConnection]:
    """One transaction per request: committed when the route returns, rolled back when it raises."""
    engine: AsyncEngine = request.app.state.engine
    async with engine.begin() as conn:
        yield conn


Conn = Annotated[AsyncConnection, Depends(connection)]


async def principal(request: Request, conn: Conn) -> Principal:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized("Sign in to Glyphh: send your access token as a Bearer token.")
    who = await principal_for(conn, token)
    context.user_id.set(str(who.user_id))
    context.org_id.set(str(who.org_id))
    return who


Caller = Annotated[Principal, Depends(principal)]
