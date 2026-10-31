"""What an org uses that its plan sells: the precedents its fullest runtime holds against the plan's precedents per
node; with Ada Cloud on, its precedents and reads this month against the plan's cloud limits (glyphh_ada/usage.py)."""

import uuid

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada.usage import CloudUsage, cloud_usage
from glyphh_server.models import Rrotor, User
from glyphh_server.ops.plans import PlanView, org_plan


class Precedents(BaseModel):
    used: int = Field(description="The most any one of the org's runtimes holds, as it last said")
    limit: int | None = Field(description="The plan's precedents per node; null = unlimited")


class Usage(BaseModel):
    plan: PlanView
    precedents: Precedents
    cloud: CloudUsage | None = Field(None, description="Ada Cloud's precedents and reads; null while it is off")


async def precedents_used(conn: AsyncConnection, org_id: uuid.UUID) -> int:
    people = select(User.id).where(User.org_id == org_id)
    held = select(func.coalesce(func.max(Rrotor.precedents), 0)).where(Rrotor.user_id.in_(people))
    return int((await conn.execute(held)).scalar_one())


async def usage(conn: AsyncConnection, org_id: uuid.UUID, cloud: Redis | None = None) -> Usage:
    """The org's use of its plan; with Ada Cloud on (`cloud`, the Redis its reads are counted on), its cloud use too.
    The connection has entered the org."""
    plan = await org_plan(conn, org_id, cloud is not None)
    used = Precedents(used=await precedents_used(conn, org_id), limit=plan.limits.precedents)
    ada = None if cloud is None else await cloud_usage(conn, cloud, org_id)
    return Usage(plan=plan, precedents=used, cloud=ada)
