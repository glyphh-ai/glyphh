"""Making an org: on Free's newest version, its one user the admin. A person's first sign-in does it, and so does
being removed from an org (everyone is always in exactly one)."""

import uuid

from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.db.seed import FREE
from glyphh_server.models import Org, User
from glyphh_server.ops.plans import newest_version


def org_name(name: str | None, email: str) -> str:
    return f"{name or email.split('@')[0]}'s org"


async def _new_org(conn: AsyncConnection, name: str) -> uuid.UUID:
    free = await newest_version(conn, FREE)
    return (await conn.execute(insert(Org).values(name=name, plan_version_id=free.id).returning(Org.id))).scalar_one()


async def _crown(conn: AsyncConnection, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
    await conn.execute(update(Org).where(Org.id == org_id).values(admin_user_id=user_id))


async def new_person(conn: AsyncConnection, email: str, name: str | None) -> uuid.UUID:
    """A new person with their own Free org, its admin."""
    org_id = await _new_org(conn, org_name(name, email))
    user_id = (
        await conn.execute(insert(User).values(org_id=org_id, email=email, name=name, role="admin").returning(User.id))
    ).scalar_one()
    await _crown(conn, org_id, user_id)
    return user_id


async def own_org(conn: AsyncConnection, user_id: uuid.UUID, name: str | None, email: str) -> uuid.UUID:
    """Move an existing person into a new Free org of their own, as its admin."""
    org_id = await _new_org(conn, org_name(name, email))
    await conn.execute(update(User).where(User.id == user_id).values(org_id=org_id, role="admin"))
    await _crown(conn, org_id, user_id)
    return org_id
