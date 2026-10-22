"""Ada Cloud's API keys (`glyphh_ak_…`): made by a signed-in person, shown once, kept as a SHA-256 in runtime_keys with
scope `cloud`. A key acts in its maker's org, with its clearance (0 to 1): what of a model's roles a read through it
may see and what votes for it (the spec's security_weight). A request may ask for less clearance, never more. Revoked
or expired, it lets nothing in (within the API's key cache, KEY_TTL seconds)."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field
from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import RuntimeKey, User
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import make_secret
from glyphh_server.ops.runtime_keys import expiry, key_hash

PREFIX: str = "glyphh_ak_"
CLOUD: str = "cloud"


class CloudKey(BaseModel):
    id: uuid.UUID
    name: str
    clearance: float = Field(description="0 to 1: what of a model's secured roles a call with this key may read")
    created_at: datetime
    expires_at: datetime | None = Field(description="When the key stops working; null never expires")
    revoked_at: datetime | None


class MadeCloudKey(CloudKey):
    key: str = Field(description="The key itself: shown once, never stored")


class KeyHolder(BaseModel):
    """Who a key acts for: its maker, their org, the key's clearance."""

    key_id: uuid.UUID
    user_id: uuid.UUID
    org_id: uuid.UUID
    clearance: float


_COLUMNS = (
    RuntimeKey.id,
    RuntimeKey.name,
    RuntimeKey.clearance,
    RuntimeKey.created_at,
    RuntimeKey.expires_at,
    RuntimeKey.revoked_at,
)
_live = (
    RuntimeKey.scope == CLOUD,
    RuntimeKey.revoked_at.is_(None),
    or_(RuntimeKey.expires_at.is_(None), RuntimeKey.expires_at > func.now()),
)


async def create(conn: AsyncConnection, who: Principal, name: str, days: int | None, clearance: float) -> MadeCloudKey:
    key = PREFIX + make_secret()
    values = {"user_id": who.user_id, "name": name, "key_hash": key_hash(key), "scope": CLOUD}
    values |= {"expires_at": expiry(days), "clearance": Decimal(str(round(clearance, 3)))}
    row = (await conn.execute(insert(RuntimeKey).values(**values).returning(*_COLUMNS))).one()
    return MadeCloudKey(**row._mapping, key=key)


async def listing(conn: AsyncConnection, who: Principal) -> list[CloudKey]:
    mine = select(*_COLUMNS).where(RuntimeKey.user_id == who.user_id, RuntimeKey.scope == CLOUD)
    return [CloudKey(**r._mapping) for r in await conn.execute(mine.order_by(RuntimeKey.created_at, RuntimeKey.id))]


async def revoke(conn: AsyncConnection, who: Principal, key_id: uuid.UUID) -> CloudKey:
    mine = (
        update(RuntimeKey)
        .where(RuntimeKey.id == key_id, RuntimeKey.user_id == who.user_id, *_live)
        .values(revoked_at=func.now())
        .returning(*_COLUMNS)
    )
    row = (await conn.execute(mine)).first()
    if row is None:
        raise NotFound("You have no such live API key.", key_id=str(key_id))
    return CloudKey(**row._mapping)


async def holder(conn: AsyncConnection, key: str) -> KeyHolder | None:
    """The live cloud key behind a bearer, found by its hash before anyone is known (no org set yet)."""
    found = select(RuntimeKey.id, RuntimeKey.user_id, User.org_id, RuntimeKey.clearance).join(
        User, User.id == RuntimeKey.user_id
    )
    row = (await conn.execute(found.where(RuntimeKey.key_hash == key_hash(key), *_live))).first()
    if row is None:
        return None
    return KeyHolder(key_id=row.id, user_id=row.user_id, org_id=row.org_id, clearance=float(row.clearance))
