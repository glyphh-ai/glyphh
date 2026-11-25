"""The people in an org. The admin removes members, never themselves: a removed member keeps their account, in a
new Free org of their own."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.db import tenancy
from glyphh_server.errors import Forbidden, NotFound
from glyphh_server.models import User
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.guards import require_admin
from glyphh_server.ops.orgs import own_org


class Member(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    role: str
    joined_at: datetime


_COLUMNS = (User.id, User.email, User.name, User.role, User.created_at.label("joined_at"))


async def list_members(conn: AsyncConnection, who: Principal) -> list[Member]:
    rows = await conn.execute(select(*_COLUMNS).where(User.org_id == who.org_id).order_by(User.created_at))
    return [Member(**r._mapping) for r in rows]


async def remove_member(conn: AsyncConnection, who: Principal, user_id: uuid.UUID) -> None:
    require_admin(who)
    row = (await conn.execute(select(*_COLUMNS).where(User.id == user_id, User.org_id == who.org_id))).first()
    if row is None:
        raise NotFound("That person isn't in your org.", user_id=str(user_id))
    if row.role == "admin":
        raise Forbidden("The admin can't be removed from their org.")
    await tenancy.leave(conn)  # their new org is not this one
    await own_org(conn, user_id, row.name, row.email)
