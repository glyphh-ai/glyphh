"""Plan limits, checked at the moment they would be crossed. A refusal is E_LIMIT naming the limit, what is used,
the most allowed and the plan that would lift it. Callers lock the row the count belongs to first, so requests at
the same moment are taken one after another."""

import uuid
from collections.abc import Callable

from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import LimitReached
from glyphh_server.models import Install, Invite, Org, User
from glyphh_server.ops.plans import newest_versions

# Each limit the server sees used, and the plan version's column that holds it.
ALLOWED: dict[str, Callable[[Row], int | None]] = {
    "members": lambda row: row.max_members,
    "installs": lambda row: row.max_installs,
}


async def lifting_plan(conn: AsyncConnection, limit: str, used: int) -> str | None:
    """The first plan (in the plans' order) whose newest version allows one more."""
    for row in await newest_versions(conn):
        allowed = ALLOWED[limit](row)
        if allowed is None or allowed > used:
            return row.name
    return None


async def check(conn: AsyncConnection, limit: str, used: int, version: Row) -> None:
    allowed = ALLOWED[limit](version)
    if allowed is None or used < allowed:
        return
    lift = await lifting_plan(conn, limit, used)
    then = f" {lift} allows more." if lift else " Remove one first."
    raise LimitReached(
        f"Your {version.name} plan allows {allowed} {limit}.{then}", limit=limit, used=used, max=allowed, plan=lift
    )


def check_seats(used: int, seats: int, version: Row) -> None:
    if used >= seats:
        raise LimitReached(
            f"All {seats} of your seats are taken. Add seats, or revoke an invite.",
            limit="seats",
            used=used,
            max=seats,
            plan=version.name,
        )


async def lock_org(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    await conn.execute(select(Org.id).where(Org.id == org_id).with_for_update())


async def lock_user(conn: AsyncConnection, user_id: uuid.UUID) -> None:
    await conn.execute(select(User.id).where(User.id == user_id).with_for_update())


async def _count(conn: AsyncConnection, *where: object) -> int:
    return int((await conn.execute(select(func.count()).where(*where))).scalar_one())


async def members(conn: AsyncConnection, org_id: uuid.UUID) -> int:
    return await _count(conn, User.org_id == org_id)


async def open_invites(conn: AsyncConnection, org_id: uuid.UUID) -> int:
    return await _count(conn, Invite.org_id == org_id, Invite.accepted_at.is_(None), Invite.expires_at > func.now())


async def seats_taken(conn: AsyncConnection, org_id: uuid.UUID) -> int:
    """Members, and the open invites that each hold a seat."""
    return await members(conn, org_id) + await open_invites(conn, org_id)


async def installs(conn: AsyncConnection, user_id: uuid.UUID) -> int:
    """Active installs: the person's machines, since a machine has at most one."""
    return await _count(conn, Install.user_id == user_id, Install.revoked_at.is_(None))
