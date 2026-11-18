"""What staff may still change on an org: suspending it, and lifting that. Suspended, its people's tokens are refused
until it is lifted (api/auth.py); nothing of its data changes. Each is audited by the request's row. (Granting
Enterprise, changing a plan version and granting balance went with the products they managed, 2026-11-18.)"""

import uuid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import Org


class Suspension(BaseModel):
    reason: str = Field(min_length=3, max_length=500, description="Why, kept with it and in the audit log")


async def _org(conn: AsyncConnection, org_id: uuid.UUID) -> Any:
    row = (await conn.execute(select(Org.id, Org.suspended_at).where(Org.id == org_id).with_for_update())).first()
    if row is None:
        raise NotFound("There is no such org.", org_id=str(org_id))
    return row


async def suspend(conn: AsyncConnection, org_id: uuid.UUID, reason: str, own_org: uuid.UUID) -> None:
    if org_id == own_org:
        raise Conflict("You can't suspend your own org.", reason="own_org")
    org = await _org(conn, org_id)
    if org.suspended_at is not None:
        raise Conflict("The org is suspended already.", reason="suspended")
    await conn.execute(
        update(Org).where(Org.id == org_id).values(suspended_at=func.now(), suspended_reason=reason.strip())
    )


async def unsuspend(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    org = await _org(conn, org_id)
    if org.suspended_at is None:
        raise Conflict("The org is not suspended.", reason="not_suspended")
    await conn.execute(update(Org).where(Org.id == org_id).values(suspended_at=None, suspended_reason=None))
