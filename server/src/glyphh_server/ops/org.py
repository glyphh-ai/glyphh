"""The member's org: its name, its plan and how many of its seats are taken."""

import uuid

from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Invite, Org, Plan, User
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.guards import require_admin


class OrgView(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    seats_taken: int
    max_seats: int | None = Field(description="null = no limit")


async def _seats_taken(conn: AsyncConnection, org_id: uuid.UUID) -> int:
    users = select(func.count()).select_from(User).where(User.org_id == org_id, User.disabled_at.is_(None))
    invites = (
        select(func.count())
        .select_from(Invite)
        .where(
            Invite.org_id == org_id,
            Invite.accepted_at.is_(None),
            Invite.revoked_at.is_(None),
            Invite.expires_at > func.now(),
        )
    )
    return int((await conn.execute(select(users.scalar_subquery() + invites.scalar_subquery()))).scalar_one())


async def get_org(conn: AsyncConnection, who: Principal) -> OrgView:
    row = (
        await conn.execute(
            select(Org.id, Org.name, Plan.name.label("plan"), Plan.max_seats)
            .join(Plan, Plan.id == Org.plan_id)
            .where(Org.id == who.org_id)
        )
    ).one()
    return OrgView(
        id=row.id,
        name=row.name,
        plan=row.plan,
        max_seats=row.max_seats,
        seats_taken=await _seats_taken(conn, who.org_id),
    )


async def rename_org(conn: AsyncConnection, who: Principal, name: str) -> OrgView:
    require_admin(who)
    await conn.execute(update(Org).where(Org.id == who.org_id).values(name=name.strip()))
    return await get_org(conn, who)
