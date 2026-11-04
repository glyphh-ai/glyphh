"""The reads an org makes of Ada Cloud, by calendar month (docs/specs/ada-cloud.md, section 7): what a plan's
cloud_requests counts. A read is decide, query, probabilities or facts (by the API, the connector or /v1/runs); a
decide of several outputs counts once per output; a beam (api/beam.py) counts one read per hop it reaches, under its
own name, however many values that hop is asked about; nothing else counts.

Counted in Redis as they are made (api/meter.py): `ada:req:<org>:<YYYY-MM>`, the month's count, and
`ada:reqp:<org>:<YYYY-MM>`, what the database has not been told yet, with the org in `ada:req:orgs:<YYYY-MM>`. The
server's minute tick adds what is pending to `ada_usage` (flush). A month's count Redis no longer has (lost, or the
month's first read) starts from the database's, so losing Redis loses at most a minute of reads."""

import uuid
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_ada.protocol import READS
from glyphh_server.db import tenancy
from glyphh_server.models import AdaUsage, Org

KEPT_SECONDS: int = 40 * 86_400  # a month's keys outlive the month, so the tick after it ends flushes them
BEAM: str = "beam"  # a beam's hop, counted by the API itself (never a worker's op): one read per hop reached


def period(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m")


def turns(month: str) -> str:
    """The day the month's reads start again: the next month's first, YYYY-MM-DD."""
    year, mon = (int(p) for p in month.split("-"))
    return f"{year + mon // 12:04d}-{mon % 12 + 1:02d}-01"


def before(month: str) -> str:
    year, mon = (int(p) for p in month.split("-"))
    return f"{year - (mon == 1):04d}-{(mon - 2) % 12 + 1:02d}"


def total_key(org: object, month: str) -> str:
    return f"ada:req:{org}:{month}"


def pending_key(org: object, month: str) -> str:
    return f"ada:reqp:{org}:{month}"


def orgs_key(month: str) -> str:
    return f"ada:req:orgs:{month}"


def reads(op: str, args: dict[str, Any]) -> int:
    """How many requests a call is: a read is one (a beam's hop too), a decide of several outputs one per output,
    anything else none."""
    if op == BEAM:
        return 1
    if op not in READS:
        return 0
    return max(1, len(args.get("outputs") or []))


async def kept(conn: AsyncConnection, org_id: uuid.UUID, month: str) -> int:
    """The month's reads the database has (the tick's)."""
    found = select(AdaUsage.requests).where(AdaUsage.org_id == org_id, AdaUsage.period == month)
    return int((await conn.execute(found)).scalar() or 0)


async def used(redis: Redis, conn: AsyncConnection, org_id: uuid.UUID, month: str) -> int:
    """The month's reads: Redis's count, else the database's."""
    counted = await redis.get(total_key(org_id, month))
    return int(counted) if counted is not None else await kept(conn, org_id, month)


async def _add(engine: AsyncEngine, org: uuid.UUID, month: str, n: int) -> bool:
    """The reads added to the org's month; False when the org is gone (its count goes with it)."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, org)
        if (await conn.execute(select(Org.id).where(Org.id == org))).first() is None:
            return False
        made = upsert(AdaUsage).values(org_id=org, period=month, requests=n)
        more = {"requests": AdaUsage.requests + n, "updated_at": datetime.now(UTC)}
        await conn.execute(made.on_conflict_do_update(index_elements=[AdaUsage.org_id, AdaUsage.period], set_=more))
    return True


async def flush(engine: AsyncEngine, redis: Redis, now: datetime | None = None) -> int:
    """Every org's reads the database has not been told of, this month's and the last's, added to ada_usage; answers
    how many. What is pending is taken from Redis first (a read counted meanwhile stays pending for the next tick).
    An org told of a month that has ended, or gone, leaves that month's set."""
    flushed = 0
    month = period(now)
    for each in (before(month), month):
        for org in await redis.smembers(orgs_key(each)):  # type: ignore[misc]
            told = each != month  # an ended month: no read can come to it now
            n = int(await redis.get(pending_key(org, each)) or 0)
            if n > 0:
                await redis.decrby(pending_key(org, each), n)
                if await _add(engine, uuid.UUID(org), each, n):
                    flushed += n
                else:
                    told = True  # the org is gone
            if told:
                await redis.srem(orgs_key(each), org)  # type: ignore[misc]
    return flushed
