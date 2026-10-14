"""Who am I: the person, their org and role, the plan version and its limits, and what is used."""

import uuid

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Identity, Org, User
from glyphh_server.ops import limits
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.plans import PlanView, org_version, view


class MeOrg(BaseModel):
    id: uuid.UUID
    name: str
    seats: int
    billing_status: str


class Used(BaseModel):
    members: int
    seats: int
    installs: int
    workspaces: int


class Me(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    role: str
    providers: list[str]
    org: MeOrg
    plan: PlanView
    used: Used


async def me(conn: AsyncConnection, who: Principal) -> Me:
    person = (await conn.execute(select(User.email, User.name, User.role).where(User.id == who.user_id))).one()
    org = (
        await conn.execute(select(Org.id, Org.name, Org.seats, Org.billing_status).where(Org.id == who.org_id))
    ).one()
    providers = await conn.execute(
        select(Identity.provider).where(Identity.user_id == who.user_id).order_by(Identity.provider)
    )
    used = Used(
        members=await limits.members(conn, who.org_id),
        seats=await limits.seats_taken(conn, who.org_id),
        installs=await limits.installs(conn, who.user_id),
        workspaces=await limits.workspaces(conn, who.user_id),
    )
    return Me(
        id=who.user_id,
        email=person.email,
        name=person.name,
        role=person.role,
        providers=list(providers.scalars()),
        org=MeOrg(**org._mapping),
        plan=view(await org_version(conn, who.org_id)),
        used=used,
    )


async def rename_me(conn: AsyncConnection, who: Principal, name: str) -> Me:
    await conn.execute(update(User).where(User.id == who.user_id).values(name=name.strip()))
    return await me(conn, who)
