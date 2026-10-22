"""What an org uses of Ada Cloud against its plan (docs/specs/ada-cloud.md, section 7): its live models, the precedents
their active stores hold together (what the cap counts, read from its schema as a worker counts them) and its reads
this month (requests.py), with the plan's numbers beside them. Read on a connection that has entered the org, so its
schema's row-level security lets the count through.

One shape for the Ada API's GET /v1/usage, the account API's usage (`cloud`) and the connector's usage tool:
{plan, month, resets_at, models, precedents: {used, max}, requests: {used, max, over, overage},
requests_per_second}."""

import uuid

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada import requests
from glyphh_ada.allowance import allowance
from glyphh_ada.pg import schema_for

HELD: str = """
    SELECT count(*), coalesce(sum(c.n), 0) FROM {s}.models m
    JOIN {s}.spec_versions v ON v.model_id = m.id AND v.version = m.active_version
    LEFT JOIN {s}.counts c ON c.model = v.store WHERE m.deleted_at IS NULL
"""


class Held(BaseModel):
    used: int = Field(description="Precedents the org's models hold together")
    max: int | None = Field(description="The plan's precedents; null = by contract")


class Reads(BaseModel):
    used: int = Field(description="Reads this month: decide, query, probabilities, facts (a decide per output)")
    max: int | None = Field(description="The plan's reads a month; null = by contract")
    over: int = Field(description="Reads past the month's, metered (Basic, Pro, Team)")
    overage: bool = Field(description="Reads past the month are metered; false: refused until it turns")


class CloudUsage(BaseModel):
    plan: str = Field(description="The org's plan")
    month: str = Field(description="The calendar month counted, YYYY-MM, UTC")
    resets_at: str = Field(description="When the month's count starts again, YYYY-MM-DD")
    models: int = Field(description="The org's live models")
    precedents: Held
    requests: Reads
    requests_per_second: int | None = Field(description="The plan's calls a second; null = by contract")


async def held(conn: AsyncConnection, org_id: uuid.UUID) -> tuple[int, int]:
    """The org's live models, and the precedents their active stores hold together; nothing before its first."""
    schema = f'"{schema_for(str(org_id))}"'
    if (await conn.execute(text("SELECT to_regclass(:t)"), {"t": f"{schema}.counts"})).scalar() is None:
        return 0, 0
    models, precedents = (await conn.execute(text(HELD.format(s=schema)))).one()
    return int(models), int(precedents)


async def cloud_usage(conn: AsyncConnection, redis: Redis, org_id: uuid.UUID) -> CloudUsage:
    plan, month = await allowance(conn, org_id), requests.period()
    made = await requests.used(redis, conn, org_id, month)
    over = max(0, made - plan.requests) if plan.requests is not None and plan.overage else 0
    models, precedents = await held(conn, org_id)
    return CloudUsage(
        plan=plan.plan,
        month=month,
        resets_at=requests.turns(month),
        models=models,
        precedents=Held(used=precedents, max=plan.precedents),
        requests=Reads(used=made, max=plan.requests, over=over, overage=plan.overage),
        requests_per_second=plan.rps,
    )
