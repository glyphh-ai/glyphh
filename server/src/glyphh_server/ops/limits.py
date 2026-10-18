"""The one plan limit the server sees used: a person's hosted machines, checked when one more would be made, and
when one is started (a person holding more than their org's plan allows starts none: ops/held.py). A
refusal is E_LIMIT naming the limit, what is used, the most allowed and the plan that would lift it. Members,
installs and models are unlimited on every plan. Callers lock the row the count belongs to first, so requests at
the same moment are taken one after another."""

import uuid

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import LimitReached
from glyphh_server.models import Org, Rrotor, User
from glyphh_server.ops.plans import newest_versions

MACHINES: str = "machines"


async def lifting_plan(conn: AsyncConnection, used: int) -> str | None:
    """The first self-serve plan (in the plans' order) whose newest version allows one more machine, else the first
    that does."""
    roomy = [r for r in await newest_versions(conn) if r.max_machines is None or r.max_machines > used]
    return next((r.name for r in roomy if r.self_serve), roomy[0].name if roomy else None)


async def check_machines(conn: AsyncConnection, used: int, version: Row, more: int = 1) -> None:
    """`more` machines on top of the `used` ones fit the plan: one more to make one, none to start one of those held."""
    allowed = version.max_machines
    if allowed is None or used + more <= allowed:
        return
    lift = await lifting_plan(conn, used + more - 1)
    then = f" {lift} allows more." if lift else " Remove one first."
    said = "no hosted machines" if allowed == 0 else f"{allowed} hosted machines"
    raise LimitReached(
        f"Your {version.name} plan allows {said}.{then}",
        reason=MACHINES,
        limit=MACHINES,
        used=used,
        max=allowed,
        plan=lift,
    )


async def lock_org(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    await conn.execute(select(Org.id).where(Org.id == org_id).with_for_update())


async def lock_user(conn: AsyncConnection, user_id: uuid.UUID) -> None:
    await conn.execute(select(User.id).where(User.id == user_id).with_for_update())


async def _count(conn: AsyncConnection, *where: object) -> int:
    return int((await conn.execute(select(func.count()).where(*where))).scalar_one())


async def members(conn: AsyncConnection, org_id: uuid.UUID) -> int:
    return await _count(conn, User.org_id == org_id)


async def machines(conn: AsyncConnection, user_id: uuid.UUID) -> int:
    """The person's hosted machines; self-hosted runtimes are not counted."""
    return await _count(conn, Rrotor.user_id == user_id, Rrotor.mode == "hosted")


async def most_held(conn: AsyncConnection, org_id: uuid.UUID) -> int:
    """The most hosted machines any one of the org's people holds."""
    people = select(User.id).where(User.org_id == org_id)
    each = (
        select(func.count().label("n"))
        .where(Rrotor.user_id.in_(people), Rrotor.mode == "hosted")
        .group_by(Rrotor.user_id)
        .subquery()
    )
    return int((await conn.execute(select(func.coalesce(func.max(each.c.n), 0)))).scalar_one())
