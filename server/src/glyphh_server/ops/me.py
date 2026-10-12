"""Who am I: the signed-in person, the org this token acts in, and every org they belong to. The same functions
behind the API and MCP."""

import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Membership, Org, Plan, User
from glyphh_server.ops.auth.principal import Principal


class MeOrg(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    personal: bool
    role: str


class Me(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    image_url: str | None
    role: str
    org: MeOrg


async def my_orgs(conn: AsyncConnection, user_id: uuid.UUID) -> list[MeOrg]:
    """Every org the person belongs to (not disabled in), their Personal org first."""
    rows = await conn.execute(
        select(Org.id, Org.name, Plan.name.label("plan"), Org.personal_user_id, Membership.role)
        .join(Membership, Membership.org_id == Org.id)
        .join(Plan, Plan.id == Org.plan_id)
        .where(Membership.user_id == user_id, Membership.disabled_at.is_(None))
        .order_by(Org.personal_user_id.is_(None), Org.name)
    )
    return [
        MeOrg(id=r.id, name=r.name, plan=r.plan, personal=r.personal_user_id is not None, role=r.role) for r in rows
    ]


async def me(conn: AsyncConnection, principal: Principal) -> Me:
    person = (
        await conn.execute(
            select(User.id, User.email, User.first_name, User.last_name, User.image_url).where(
                User.id == principal.user_id
            )
        )
    ).one()
    org = next(o for o in await my_orgs(conn, principal.user_id) if o.id == principal.org_id)
    return Me(
        id=person.id,
        email=person.email,
        first_name=person.first_name,
        last_name=person.last_name,
        image_url=person.image_url,
        role=org.role,
        org=org,
    )
