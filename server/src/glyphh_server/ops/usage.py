"""What an org uses that its plan sells: the precedents its fullest runtime holds against the plan's precedents per
node, and its hosted machines' month to date, all in (Fly's rates with the markup, never named), each machine's own too,
those deleted this month included; with Ada Cloud on, its precedents and reads this month against the plan's cloud
limits (glyphh_ada/usage.py)."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada.usage import CloudUsage, cloud_usage
from glyphh_server.models import MachineMonth, Rrotor, User
from glyphh_server.ops.plans import PlanView, org_plan
from glyphh_server.ops.runtimes import month_of

MICROS_PER_CENT: int = 10_000


class Precedents(BaseModel):
    used: int = Field(description="The most any one of the org's hosted or self-hosted runtimes holds, as it last said")
    limit: int | None = Field(description="The plan's precedents per node; null = unlimited")


class MachineCost(BaseModel):
    id: uuid.UUID
    name: str
    size: str
    cents: int = Field(description="This month so far")


class Hosting(BaseModel):
    month: str = Field(description="YYYY-MM, UTC")
    month_to_date_cents: int
    machines: list[MachineCost]


class Usage(BaseModel):
    plan: PlanView
    precedents: Precedents
    hosting: Hosting
    cloud: CloudUsage | None = Field(None, description="Ada Cloud's precedents and reads; null while it is off")


async def precedents_used(conn: AsyncConnection, org_id: uuid.UUID) -> int:
    people = select(User.id).where(User.org_id == org_id)
    held = select(func.coalesce(func.max(Rrotor.precedents), 0)).where(
        Rrotor.user_id.in_(people), Rrotor.mode.in_(("hosted", "self"))
    )
    return int((await conn.execute(held)).scalar_one())


async def hosting(conn: AsyncConnection, org_id: uuid.UUID) -> Hosting:
    month = month_of(datetime.now(UTC))
    rows = list(
        await conn.execute(
            select(MachineMonth.rrotor_id, MachineMonth.name, MachineMonth.size, MachineMonth.charge_micros)
            .where(MachineMonth.org_id == org_id, MachineMonth.month == month)
            .order_by(MachineMonth.name, MachineMonth.rrotor_id)
        )
    )
    machines = [
        MachineCost(id=r.rrotor_id, name=r.name, size=r.size, cents=r.charge_micros // MICROS_PER_CENT) for r in rows
    ]
    total = sum(r.charge_micros for r in rows) // MICROS_PER_CENT
    return Hosting(month=month, month_to_date_cents=total, machines=machines)


async def usage(conn: AsyncConnection, org_id: uuid.UUID, cloud: Redis | None = None) -> Usage:
    """The org's use of its plan; with Ada Cloud on (`cloud`, the Redis its reads are counted on), its cloud use too.
    The connection has entered the org."""
    plan = await org_plan(conn, org_id, cloud is not None)
    used = Precedents(used=await precedents_used(conn, org_id), limit=plan.limits.precedents)
    ada = None if cloud is None else await cloud_usage(conn, cloud, org_id)
    return Usage(plan=plan, precedents=used, hosting=await hosting(conn, org_id), cloud=ada)
