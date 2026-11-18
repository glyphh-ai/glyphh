"""The plan versions an org can be put on by the server itself: only Free's newest, for a new person's org and for an
org whose subscription has ended (ops/orgs.py, ops/billing/sync.py)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.db.seed import FREE
from glyphh_server.models import Plan, PlanVersion


async def free_version(conn: AsyncConnection) -> uuid.UUID:
    """Free's newest version (the schema step makes sure there is one, db/seed.py)."""
    newest = (
        select(PlanVersion.id)
        .join(Plan, Plan.id == PlanVersion.plan_id)
        .where(Plan.name == FREE)
        .order_by(PlanVersion.version.desc())
        .limit(1)
    )
    return (await conn.execute(newest)).scalar_one()
