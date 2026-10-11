"""Who am I: the signed-in member, their org and its plan. The same function behind the API and MCP."""

import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Org, Plan, User
from glyphh_server.ops.auth.principal import Principal


class MeOrg(BaseModel):
    id: uuid.UUID
    name: str
    plan: str


class Me(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    image_url: str | None
    role: str
    org: MeOrg


async def me(conn: AsyncConnection, principal: Principal) -> Me:
    row = (
        await conn.execute(
            select(
                User.id,
                User.email,
                User.first_name,
                User.last_name,
                User.image_url,
                User.role,
                User.org_id,
                Org.name.label("org_name"),
                Plan.name.label("plan_name"),
            )
            .join(Org, Org.id == User.org_id)
            .join(Plan, Plan.id == Org.plan_id)
            .where(User.id == principal.user_id)
        )
    ).one()
    return Me(
        id=row.id,
        email=row.email,
        first_name=row.first_name,
        last_name=row.last_name,
        image_url=row.image_url,
        role=row.role,
        org=MeOrg(id=row.org_id, name=row.org_name, plan=row.plan_name),
    )
