"""Who am I: the person, their org and role, the plan version their org is on, and what the org uses of it."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada.usage import CloudUsage
from glyphh_server.models import Identity, Org, User
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.plans import PlanView
from glyphh_server.ops.usage import Hosting, Precedents, usage


class MeOrg(BaseModel):
    id: uuid.UUID
    name: str
    billing_status: str
    renews_at: datetime | None = Field(description="When the subscription renews; null when not subscribed or ending")
    plan_until: datetime | None = Field(description="When an Enterprise grant ends; null on any other plan")


class Me(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    role: str
    providers: list[str]
    org: MeOrg
    plan: PlanView
    precedents: Precedents
    hosting: Hosting
    ada_cloud: bool = Field(False, description="Ada Cloud is on (GLYPHH_ADA_CLOUD): the platform shows Ada")
    cloud: CloudUsage | None = Field(None, description="Ada Cloud's precedents and reads; null while it is off")


async def me(conn: AsyncConnection, who: Principal, cloud: Redis | None = None) -> Me:
    """cloud: with Ada Cloud on, the Redis its reads are counted on (the plan's cloud limits and use are shown)."""
    person = (await conn.execute(select(User.email, User.name, User.role).where(User.id == who.user_id))).one()
    columns = (Org.id, Org.name, Org.billing_status, Org.renews_at, Org.plan_until)
    org = (await conn.execute(select(*columns).where(Org.id == who.org_id))).one()
    providers = await conn.execute(
        select(Identity.provider).where(Identity.user_id == who.user_id).order_by(Identity.provider)
    )
    used = await usage(conn, who.org_id, cloud)
    return Me(
        id=who.user_id,
        email=person.email,
        name=person.name,
        role=person.role,
        providers=list(providers.scalars()),
        org=MeOrg(**org._mapping),
        plan=used.plan,
        precedents=used.precedents,
        hosting=used.hosting,
        ada_cloud=cloud is not None,
        cloud=used.cloud,
    )


async def rename_me(conn: AsyncConnection, who: Principal, name: str, cloud: Redis | None = None) -> Me:
    await conn.execute(update(User).where(User.id == who.user_id).values(name=name.strip()))
    return await me(conn, who, cloud)
