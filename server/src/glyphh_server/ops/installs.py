"""A person's installs: one per device-flow approval. Revoking one signs that machine out."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import Install
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.tokens import revoke_install


class InstallView(BaseModel):
    id: uuid.UUID
    name: str
    surface: str
    mod_version: str
    last_seen_at: datetime | None
    created_at: datetime
    current: bool


async def list_installs(conn: AsyncConnection, who: Principal) -> list[InstallView]:
    rows = await conn.execute(
        select(Install.id, Install.name, Install.surface, Install.mod_version, Install.last_seen_at, Install.created_at)
        .where(Install.user_id == who.user_id, Install.revoked_at.is_(None))
        .order_by(Install.created_at)
    )
    return [InstallView(**r._mapping, current=r.id == who.install_id) for r in rows]


async def revoke(conn: AsyncConnection, who: Principal, install_id: uuid.UUID) -> None:
    mine = select(Install.id).where(
        Install.id == install_id, Install.user_id == who.user_id, Install.revoked_at.is_(None)
    )
    if (await conn.execute(mine)).first() is None:
        raise NotFound("You have no such install.", install_id=str(install_id))
    await revoke_install(conn, install_id)


async def sign_out(conn: AsyncConnection, who: Principal) -> None:
    await revoke_install(conn, who.install_id)
