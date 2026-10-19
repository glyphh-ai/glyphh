"""The caller's org: its name, its plan version, its members and what Stripe says of its billing."""

import uuid

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.models import Org
from glyphh_server.ops import limits
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.guards import require_admin
from glyphh_server.ops.plans import PlanView, org_plan


class OrgView(BaseModel):
    id: uuid.UUID
    name: str
    admin_user_id: uuid.UUID | None
    plan: PlanView
    members: int
    billing_status: str


async def org_view(conn: AsyncConnection, org_id: uuid.UUID, settings: Settings) -> OrgView:
    row = (
        await conn.execute(select(Org.id, Org.name, Org.admin_user_id, Org.billing_status).where(Org.id == org_id))
    ).one()
    return OrgView(
        **row._mapping,
        plan=await org_plan(conn, org_id, settings),
        members=await limits.members(conn, org_id),
    )


async def get_org(conn: AsyncConnection, who: Principal, settings: Settings) -> OrgView:
    return await org_view(conn, who.org_id, settings)


async def rename_org(conn: AsyncConnection, who: Principal, name: str, settings: Settings) -> OrgView:
    require_admin(who)
    await conn.execute(update(Org).where(Org.id == who.org_id).values(name=name.strip()))
    return await org_view(conn, who.org_id, settings)
