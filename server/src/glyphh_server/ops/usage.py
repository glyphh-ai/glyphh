"""What an org uses that its plan sells: the precedents its fullest runtime holds against the plan's precedents per
node; with Ada Cloud on, its precedents and reads this month against the plan's cloud limits (glyphh_ada/usage.py);
its connections to other services against the plan's included and their price; and, asked for, the tokens this month
of the Glyphh-hosted models and the bots against the plan's allowance, each model's part and charge, and the overage
balance (glyphh_server/llm/usage.py)."""

import uuid

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada.usage import CloudUsage, cloud_usage
from glyphh_server.llm import usage as llm
from glyphh_server.models import Connection, Rrotor, User
from glyphh_server.ops.bot_usage import BotMonth, bots_month
from glyphh_server.ops.plans import ConnectionPrice, PlanView, org_plan


class Precedents(BaseModel):
    used: int = Field(description="The most any one of the org's runtimes holds, as it last said")
    limit: int | None = Field(description="The plan's precedents per node; null = unlimited")


class Connections(BaseModel):
    used: int = Field(description="The org's connections to other services (Pipedream accounts), its bots' together")
    included: int | None = Field(description="The plan's connections included; null = every one")
    over: int = Field(description="Connections past the included")
    cents_a_month: int | None = Field(description="Each one past the included, a month; null = not priced")
    due_cents: int | None = Field(description="over x cents_a_month, a month; null while not priced")


class Usage(BaseModel):
    plan: PlanView
    precedents: Precedents
    cloud: CloudUsage | None = Field(None, description="Ada Cloud's precedents and reads; null while it is off")
    connections: Connections | None = Field(None, description="Connections against the plan's; null where not read")
    tokens: llm.Tokens | None = Field(
        None, description="The hosted models' and the bots' tokens this month, each model's; null where not read"
    )
    balance: llm.Balance | None = Field(None, description="The overage balance; null where not read")
    bots: list[BotMonth] | None = Field(None, description="Each bot's month: runs, tokens, charge; null where not read")


async def precedents_used(conn: AsyncConnection, org_id: uuid.UUID) -> int:
    people = select(User.id).where(User.org_id == org_id)
    held = select(func.coalesce(func.max(Rrotor.precedents), 0)).where(Rrotor.user_id.in_(people))
    return int((await conn.execute(held)).scalar_one())


async def connections_used(conn: AsyncConnection, org_id: uuid.UUID, price: ConnectionPrice) -> Connections:
    used = int((await conn.execute(select(func.count()).where(Connection.org_id == org_id))).scalar_one())
    over = 0 if price.included is None else max(0, used - price.included)
    due = None if price.cents_a_month is None else over * price.cents_a_month
    return Connections(used=used, included=price.included, over=over, cents_a_month=price.cents_a_month, due_cents=due)


async def usage(conn: AsyncConnection, org_id: uuid.UUID, cloud: Redis | None = None, tokens: bool = False) -> Usage:
    """The org's use of its plan; with Ada Cloud on (`cloud`, the Redis its reads are counted on), its cloud use too;
    with `tokens`, its connections, the month's tokens (hosted models and bots, the same meter) and the balance. The
    connection has entered the org."""
    plan = await org_plan(conn, org_id, cloud is not None)
    used = Precedents(used=await precedents_used(conn, org_id), limit=plan.limits.precedents)
    ada = None if cloud is None else await cloud_usage(conn, cloud, org_id)
    if not tokens:
        return Usage(plan=plan, precedents=used, cloud=ada)
    held = await connections_used(conn, org_id, plan.connections)
    month, balance = await llm.tokens(conn, org_id, plan.llm_tokens), await llm.balance(conn, org_id)
    bots = await bots_month(conn, org_id)
    return Usage(plan=plan, precedents=used, cloud=ada, connections=held, tokens=month, balance=balance, bots=bots)
