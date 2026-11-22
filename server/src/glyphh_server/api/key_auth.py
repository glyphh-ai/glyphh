"""Who is calling the bots' routes (/v1/bots*, /v1/bot-runs*, /v1/bot-approvals, /v1/bot-templates*): a person signed
in as anywhere else (api/auth.py), or a live Ada API key of theirs (glyphh_ak_, glyphh_ada/keys.py), so their own
code reaches their bots with the key it reaches Ada with (the SDK's bots client). The key acts as the person who made
it, in their org. A bot's own Ada key (the one its gates use, held where the bot runs, a rrotor too) is never a
person: refused, as an unknown, revoked or expired key is, with the same answer."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada import keys as ada_keys
from glyphh_server.api.auth import Bearer, Conn, authenticate
from glyphh_server.db import tenancy
from glyphh_server.errors import Unauthorized
from glyphh_server.models import RuntimeKey, User
from glyphh_server.obs import context
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots.store import KEY_NAME

BAD_KEY: str = "That API key is not a live key of yours: make one in Glyphh (API keys)."


async def _keyed(conn: AsyncConnection, key: str) -> Principal:
    held = await ada_keys.holder(conn, key)
    if held is None:
        raise Unauthorized(BAD_KEY)
    mine = select(User.role, User.email, RuntimeKey.name).join(RuntimeKey, RuntimeKey.user_id == User.id)
    found = (await conn.execute(mine.where(RuntimeKey.id == held.key_id))).one()
    if found.name.startswith(KEY_NAME):
        raise Unauthorized(BAD_KEY)
    context.user_id.set(str(held.user_id))
    context.org_id.set(str(held.org_id))
    await tenancy.enter(conn, held.org_id)
    return Principal(user_id=held.user_id, org_id=held.org_id, role=found.role, email=found.email)


async def signed_in(conn: AsyncConnection, creds: HTTPAuthorizationCredentials | None, resource: str) -> Principal:
    """The caller: an Ada API key's person, else whoever api/auth.py finds behind the token."""
    if creds is not None and creds.credentials.startswith(ada_keys.PREFIX):
        return await _keyed(conn, creds.credentials)
    return await authenticate(conn, creds, resource)


async def caller(request: Request, conn: Conn, creds: Bearer) -> Principal:
    return await signed_in(conn, creds, request.app.state.settings.mcp_resource)


async def person(request: Request, creds: Bearer) -> Principal:
    """The caller, signed in on a transaction that has ended by the time the route's work begins."""
    async with request.app.state.engine.begin() as conn:
        return await signed_in(conn, creds, request.app.state.settings.mcp_resource)


KeyCaller = Annotated[Principal, Depends(caller)]
KeyPerson = Annotated[Principal, Depends(person)]
