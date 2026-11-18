"""Who am I: the person, their org and role, and whether they are Glyphh's staff."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Identity, Org, User
from glyphh_server.ops.auth.principal import Principal


class MeOrg(BaseModel):
    id: uuid.UUID
    name: str
    billing_status: str
    renews_at: datetime | None = Field(description="When the subscription renews; null when not subscribed or ending")
    plan_until: datetime | None = Field(description="When an Enterprise deal ends; null on any other plan")


class Me(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None
    role: str
    providers: list[str]
    org: MeOrg
    staff: bool = Field(description="Glyphh's staff (GLYPHH_STAFF_EMAILS): the platform opens the staff view")


async def me(conn: AsyncConnection, who: Principal, staff: bool) -> Me:
    person = (await conn.execute(select(User.email, User.name, User.role).where(User.id == who.user_id))).one()
    columns = (Org.id, Org.name, Org.billing_status, Org.renews_at, Org.plan_until)
    org = (await conn.execute(select(*columns).where(Org.id == who.org_id))).one()
    providers = await conn.execute(
        select(Identity.provider).where(Identity.user_id == who.user_id).order_by(Identity.provider)
    )
    return Me(
        id=who.user_id,
        email=person.email,
        name=person.name,
        role=person.role,
        providers=list(providers.scalars()),
        org=MeOrg(**org._mapping),
        staff=staff,
    )
