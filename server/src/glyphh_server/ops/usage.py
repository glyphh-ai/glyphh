"""What an org uses that its plan sells: with Ada Cloud on, its precedents and reads this month against the plan's
cloud limits (glyphh_ada/usage.py); and, asked for, the tokens this month of the Glyphh-hosted models against the
plan's allowance, each model's part and charge, and the overage balance (glyphh_server/llm/usage.py)."""

import uuid

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada.usage import CloudUsage, cloud_usage
from glyphh_server.llm import usage as llm
from glyphh_server.ops.plans import PlanView, org_plan


class Usage(BaseModel):
    plan: PlanView
    cloud: CloudUsage | None = Field(None, description="Ada Cloud's precedents and reads; null while it is off")
    tokens: llm.Tokens | None = Field(
        None, description="The hosted models' tokens this month, each model's; null where not read"
    )
    balance: llm.Balance | None = Field(None, description="The overage balance; null where not read")


async def usage(conn: AsyncConnection, org_id: uuid.UUID, cloud: Redis | None = None, tokens: bool = False) -> Usage:
    """The org's use of its plan; with Ada Cloud on (`cloud`, the Redis its reads are counted on), its cloud use too;
    with `tokens`, the month's tokens and the balance. The connection has entered the org."""
    plan = await org_plan(conn, org_id, cloud is not None)
    ada = None if cloud is None else await cloud_usage(conn, cloud, org_id)
    if not tokens:
        return Usage(plan=plan, cloud=ada)
    month, balance = await llm.tokens(conn, org_id, plan.llm_tokens), await llm.balance(conn, org_id)
    return Usage(plan=plan, cloud=ada, tokens=month, balance=balance)
