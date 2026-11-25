"""What an org's plan allows of Ada Cloud (docs/specs/ada-cloud.md, section 7), resolved with the caller (api/auth.py,
the connector) from the plan version the org is pinned to, and carried with it: the precedents it may hold across its
models (each write's cap, in the worker's message), the reads it may make a calendar month and whether those past it
are metered or refused, and the calls it may make a second. None: unlimited (by contract)."""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.ops.plans import newest_versions, org_version


@dataclass(frozen=True)
class Allowance:
    plan: str
    precedents: int | None
    requests: int | None
    rps: int | None
    overage: bool


async def allowance(conn: AsyncConnection, org_id: uuid.UUID) -> Allowance:
    row = await org_version(conn, org_id)
    return Allowance(row.name, row.cloud_precedents, row.cloud_requests, row.cloud_rps, row.cloud_overage)


async def upgrade_to(conn: AsyncConnection, now: Allowance) -> str | None:
    """The first self-serve plan whose reads go past this one's month (metered, or a bigger month); None when none
    does (talk to sales)."""
    for row in await newest_versions(conn):
        roomier = row.cloud_overage or (row.cloud_requests or 0) > (now.requests or 0)
        if row.self_serve and row.name != now.plan and roomier:
            return str(row.name)
    return None
