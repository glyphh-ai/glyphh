"""The org's own Anthropic API key (BYOK): its bots' agent steps run on it and the org pays Anthropic for the tokens
itself, nothing charged here. Kept sealed (ops/auth/sealed.py), shown only by its last four characters; a key is
tried with Anthropic before it is kept. Without one, the bots run on Glyphh's key, billed by tokens."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid
from glyphh_server.models import BotKey
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.sealed import seal, unseal
from glyphh_server.ops.bots.views import KeyView

Check = Callable[[str], Awaitable[str | None]]  # a key, tried: None when Anthropic takes it, else why not


async def anthropic_check(key: str) -> str | None:
    import anthropic

    async with anthropic.AsyncAnthropic(api_key=key, max_retries=1) as client:
        try:
            await client.models.list(limit=1)
        except anthropic.AuthenticationError:
            return "Anthropic does not take that key."
        except anthropic.PermissionDeniedError:
            return "That key may not use the Claude API."
    return None


def view(row: Any, glyphh_key: bool) -> KeyView:
    if row is None:
        return KeyView(set=False, hint="", set_at=None, glyphh_key=glyphh_key)
    return KeyView(set=True, hint=row.hint, set_at=row.set_at, glyphh_key=glyphh_key)


async def get(conn: AsyncConnection) -> Any:
    """The org's key row (RLS: only its own), or None."""
    return (await conn.execute(select(BotKey))).first()


async def own(conn: AsyncConnection, secret: str) -> str | None:
    """The org's own key, opened; None when it has none."""
    found = await get(conn)
    return None if found is None else unseal(secret, found.anthropic_key)


async def put(conn: AsyncConnection, who: Principal, secret: str, key: str, check: Check) -> Any:
    key = key.strip()
    if not key.startswith("sk-ant-"):
        raise Invalid("An Anthropic API key starts sk-ant-.", reason="key")
    if why := await check(key):
        raise Invalid(why, reason="key")
    values = {"org_id": who.org_id, "anthropic_key": seal(secret, key), "hint": key[-4:], "set_by": who.user_id}
    kept = insert(BotKey).values(**values)
    again = {**values, "set_at": func.now()}
    await conn.execute(kept.on_conflict_do_update(index_elements=[BotKey.org_id], set_=again))
    found = await get(conn)
    assert found is not None
    return found


async def remove(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    await conn.execute(delete(BotKey).where(BotKey.org_id == org_id))
