"""Runtime keys: what calls a person's hosted machines at `https://<machine>.glyphh.app`, or a self-hosted runtime at
its own address (REST and its MCP). A key names one machine or self-hosted runtime, or none: then it is good on every
hosted machine of the person's, those made later too. Made here, shown once, kept as a SHA-256; the live list of hashes
reaches rrotor in its `welcome` and, when it changes, as `keys` down the link (best effort: a runtime that is stopped
gets the list when it next links). A key expires 1 to 365 days after it is made, or never; an expired one leaves the
list, sent down the link by the server's minute tick."""

import hashlib
import logging
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import ColumnElement, and_, delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, Invalid, NotFound
from glyphh_server.models import Rrotor, RuntimeKey, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops import self_hosted
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import make_secret
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.protocol import Keys

log = logging.getLogger("glyphh.runtime")

PREFIX: str = "glyphh_rk_"
MAX_DAYS: int = 365


class KeyView(BaseModel):
    id: uuid.UUID
    runtime_id: uuid.UUID | None = Field(description="The runtime it calls; null: every hosted machine of yours")
    name: str
    created_at: datetime
    expires_at: datetime | None = Field(description="When the key stops working; null never expires")
    revoked_at: datetime | None
    calls: int = Field(description="Calls the key let in, as the runtime reports them")
    last_used_at: datetime | None


class MadeKey(KeyView):
    key: str = Field(description="The key itself: shown once, never stored")


_COLUMNS = (
    RuntimeKey.id,
    RuntimeKey.rrotor_id.label("runtime_id"),
    RuntimeKey.name,
    RuntimeKey.created_at,
    RuntimeKey.expires_at,
    RuntimeKey.revoked_at,
    RuntimeKey.calls,
    RuntimeKey.last_used_at,
)


_unexpired = or_(RuntimeKey.expires_at.is_(None), RuntimeKey.expires_at > func.now())


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def held_by(runtime_id: uuid.UUID) -> ColumnElement[bool]:
    """The keys a runtime holds: those naming it, and, for a hosted machine, its owner's that name none."""
    owner = select(Rrotor.user_id).where(Rrotor.id == runtime_id, Rrotor.mode == "hosted").scalar_subquery()
    return or_(RuntimeKey.rrotor_id == runtime_id, and_(RuntimeKey.rrotor_id.is_(None), RuntimeKey.user_id == owner))


async def hashes_for(conn: AsyncConnection, runtime_id: uuid.UUID) -> list[str]:
    """The live keys' hashes, as rrotor is to hold them: neither revoked nor expired."""
    live = select(RuntimeKey.key_hash).where(held_by(runtime_id), RuntimeKey.revoked_at.is_(None), _unexpired)
    return list((await conn.execute(live.order_by(RuntimeKey.created_at))).scalars())


async def _target(conn: AsyncConnection, who: Principal, runtime_id: uuid.UUID | None) -> uuid.UUID | None:
    """The runtime a new key calls: the hosted machine or self-hosted runtime named, else none (every hosted one)."""
    if runtime_id is None:
        return None
    mine = select(Rrotor.id).where(Rrotor.id == runtime_id, Rrotor.user_id == who.user_id, Rrotor.mode == "hosted")
    if (await conn.execute(mine)).first() is not None:
        return runtime_id
    return await self_hosted.mine(conn, who, runtime_id)


async def holders(conn: AsyncConnection, user_id: uuid.UUID, runtime_id: uuid.UUID | None) -> list[uuid.UUID]:
    """The runtimes a key is on: the one it names, else every hosted machine of its owner's."""
    if runtime_id is not None:
        return [runtime_id]
    hosted = select(Rrotor.id).where(Rrotor.user_id == user_id, Rrotor.mode == "hosted")
    return list((await conn.execute(hosted)).scalars())


async def push_keys(conn: AsyncConnection, hub: Hub, runtime_id: uuid.UUID) -> bool:
    """The live list down the runtime's link; False when no process holds it (its welcome carries the list)."""
    sent = await hub.deliver(runtime_id, Keys(hashes=await hashes_for(conn, runtime_id)).model_dump(mode="json"))
    if not sent:
        log.info("keys wait for the runtime's next welcome", extra=fields(runtime=str(runtime_id)))
    return sent


async def _push_all(conn: AsyncConnection, hub: Hub, user_id: uuid.UUID, runtime_id: uuid.UUID | None) -> None:
    for held in await holders(conn, user_id, runtime_id):
        await push_keys(conn, hub, held)


async def list_keys(conn: AsyncConnection, who: Principal) -> list[KeyView]:
    rows = await conn.execute(
        select(*_COLUMNS).where(RuntimeKey.user_id == who.user_id).order_by(RuntimeKey.created_at, RuntimeKey.id)
    )
    return [KeyView(**r._mapping) for r in rows]


def expiry(days: int | None) -> datetime | None:
    """When a key made now for `days` expires; None never does. Past a year is refused."""
    if days is None:
        return None
    if not 1 <= days <= MAX_DAYS:
        raise Invalid("An API key lasts 1 to 365 days, or never expires.", reason="expiry_range", days=days)
    return datetime.now(UTC) + timedelta(days=days)


async def create_key(
    conn: AsyncConnection, hub: Hub, who: Principal, name: str, days: int | None, runtime_id: uuid.UUID | None = None
) -> MadeKey:
    expires_at = expiry(days)
    runtime_id = await _target(conn, who, runtime_id)
    key = PREFIX + make_secret()
    values = {"rrotor_id": runtime_id, "user_id": who.user_id, "name": name, "key_hash": key_hash(key)}
    values |= {"expires_at": expires_at}
    row = (await conn.execute(insert(RuntimeKey).values(**values).returning(*_COLUMNS))).one()
    await _push_all(conn, hub, who.user_id, runtime_id)
    return MadeKey(**row._mapping, key=key)


async def revoke_key(conn: AsyncConnection, hub: Hub, who: Principal, key_id: uuid.UUID) -> KeyView:
    mine = (
        update(RuntimeKey)
        .where(RuntimeKey.id == key_id, RuntimeKey.user_id == who.user_id, RuntimeKey.revoked_at.is_(None))
        .values(revoked_at=func.now())
        .returning(*_COLUMNS)
    )
    row = (await conn.execute(mine)).first()
    if row is None:
        raise NotFound("You have no such live runtime key.", key_id=str(key_id))
    await _push_all(conn, hub, who.user_id, row.runtime_id)
    return KeyView.model_validate(row._mapping, from_attributes=False)


async def delete_key(conn: AsyncConnection, who: Principal, key_id: uuid.UUID) -> None:
    """A revoked or expired key's record gone from the list; a live key is refused: revoke it first."""
    mine = select(RuntimeKey.revoked_at, _unexpired).where(RuntimeKey.id == key_id, RuntimeKey.user_id == who.user_id)
    row = (await conn.execute(mine)).first()
    if row is None:
        raise NotFound("You have no such runtime key.", key_id=str(key_id))
    revoked_at, unexpired = row
    if revoked_at is None and unexpired:
        raise Conflict("Revoke the key before deleting it.", reason="live", key_id=str(key_id))
    await conn.execute(delete(RuntimeKey).where(RuntimeKey.id == key_id))


EXPIRED = (
    select(RuntimeKey.rrotor_id, RuntimeKey.user_id, User.org_id)
    .join(User, User.id == RuntimeKey.user_id)
    .where(RuntimeKey.revoked_at.is_(None), RuntimeKey.expires_at <= func.now())
    .distinct()
)


async def push_expired(engine: AsyncEngine, hub: Hub, since: timedelta) -> list[uuid.UUID]:
    """The runtimes with a key that expired in the last `since`, each sent its live list; answers which."""
    async with engine.connect() as conn:  # the connecting role: every org's keys
        rows = list(await conn.execute(EXPIRED.where(RuntimeKey.expires_at > func.now() - since)))
    pushed: list[uuid.UUID] = []
    for row in rows:
        async with engine.begin() as conn:
            await tenancy.enter(conn, row.org_id)
            for held in await holders(conn, row.user_id, row.rrotor_id):
                if held not in pushed:
                    await push_keys(conn, hub, held)
                    pushed.append(held)
    return pushed
