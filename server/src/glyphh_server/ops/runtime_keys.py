"""Runtime keys: what calls a person's hosted runtime at `https://<machine>.glyphh.app` (REST and its MCP). Made
here, shown once, kept as a SHA-256; the live list of hashes reaches rrotor in its `welcome` and, when it changes,
as `keys` down the link (best effort: a runtime that is stopped gets the list when it next links)."""

import hashlib
import logging
import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import Rrotor, RuntimeKey
from glyphh_server.obs.logs import fields
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import make_secret
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.link.protocol import Keys

log = logging.getLogger("glyphh.runtime")

PREFIX: str = "glyphh_rk_"


class KeyView(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    revoked_at: datetime | None


class MadeKey(KeyView):
    key: str = Field(description="The key itself: shown once, never stored")


_COLUMNS = (RuntimeKey.id, RuntimeKey.name, RuntimeKey.created_at, RuntimeKey.revoked_at)


def key_hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def hashes_for(conn: AsyncConnection, runtime_id: uuid.UUID) -> list[str]:
    """The live keys' hashes, as rrotor is to hold them."""
    live = select(RuntimeKey.key_hash).where(RuntimeKey.rrotor_id == runtime_id, RuntimeKey.revoked_at.is_(None))
    return list((await conn.execute(live.order_by(RuntimeKey.created_at))).scalars())


async def _hosted(conn: AsyncConnection, who: Principal) -> uuid.UUID:
    mine = select(Rrotor.id).where(Rrotor.user_id == who.user_id, Rrotor.mode == "hosted")
    runtime_id = (await conn.execute(mine)).scalar()
    if runtime_id is None:
        raise NotFound("You have no hosted runtime yet. Start it first.", reason="no_runtime")
    return runtime_id


async def push_keys(conn: AsyncConnection, hub: Hub, runtime_id: uuid.UUID) -> bool:
    """The live list down the runtime's link; False when no process holds it (its welcome carries the list)."""
    sent = await hub.deliver(runtime_id, Keys(hashes=await hashes_for(conn, runtime_id)).model_dump(mode="json"))
    if not sent:
        log.info("keys wait for the runtime's next welcome", extra=fields(runtime=str(runtime_id)))
    return sent


async def list_keys(conn: AsyncConnection, who: Principal) -> list[KeyView]:
    rows = await conn.execute(
        select(*_COLUMNS).where(RuntimeKey.user_id == who.user_id).order_by(RuntimeKey.created_at, RuntimeKey.id)
    )
    return [KeyView(**r._mapping) for r in rows]


async def create_key(conn: AsyncConnection, hub: Hub, who: Principal, name: str) -> MadeKey:
    runtime_id = await _hosted(conn, who)
    key = PREFIX + make_secret()
    values = {"rrotor_id": runtime_id, "user_id": who.user_id, "name": name, "key_hash": key_hash(key)}
    row = (await conn.execute(insert(RuntimeKey).values(**values).returning(*_COLUMNS))).one()
    await push_keys(conn, hub, runtime_id)
    return MadeKey(**row._mapping, key=key)


async def revoke_key(conn: AsyncConnection, hub: Hub, who: Principal, key_id: uuid.UUID) -> KeyView:
    mine = (
        update(RuntimeKey)
        .where(RuntimeKey.id == key_id, RuntimeKey.user_id == who.user_id, RuntimeKey.revoked_at.is_(None))
        .values(revoked_at=func.now())
        .returning(*_COLUMNS, RuntimeKey.rrotor_id)
    )
    row = (await conn.execute(mine)).first()
    if row is None:
        raise NotFound("You have no such live runtime key.", key_id=str(key_id))
    await push_keys(conn, hub, row.rrotor_id)
    return KeyView(id=row.id, name=row.name, created_at=row.created_at, revoked_at=row.revoked_at)
