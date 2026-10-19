"""What an org uses that its plan sells: the precedents its hosted runtimes hold against the plan's managed bucket,
and its hosted machines' month to date, all in (Fly's rates with the markup, never named), each machine's own too,
those deleted this month included."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.models import MachineMonth, Rrotor, User
from glyphh_server.ops.plans import PlanView, org_plan
from glyphh_server.ops.runtimes import month_of

MICROS_PER_CENT: int = 10_000


class Precedents(BaseModel):
    used: int = Field(description="What the org's hosted runtimes hold, as each last said")
    limit: int | None = Field(description="The plan's managed bucket; null = unlimited")


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


async def precedents_used(conn: AsyncConnection, org_id: uuid.UUID) -> int:
    people = select(User.id).where(User.org_id == org_id)
    held = select(func.coalesce(func.sum(Rrotor.precedents), 0)).where(
        Rrotor.user_id.in_(people), Rrotor.mode == "hosted"
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


async def usage(conn: AsyncConnection, org_id: uuid.UUID, settings: Settings) -> Usage:
    plan = await org_plan(conn, org_id, settings)
    used = Precedents(used=await precedents_used(conn, org_id), limit=plan.limits.precedents)
    return Usage(plan=plan, precedents=used, hosting=await hosting(conn, org_id))
