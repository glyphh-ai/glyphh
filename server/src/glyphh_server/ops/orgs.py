"""Making an org: on Free's newest version, its one user the admin. A person's first sign-in does it (everyone is
always in exactly one org)."""

import uuid

from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Org, User
from glyphh_server.ops.plans import free_version


def org_name(name: str | None, email: str) -> str:
    return f"{name or email.split('@')[0]}'s org"


async def new_person(conn: AsyncConnection, email: str, name: str | None) -> uuid.UUID:
    """A new person with their own Free org, its admin."""
    values = {"name": org_name(name, email), "plan_version_id": await free_version(conn)}
    org_id = (await conn.execute(insert(Org).values(**values).returning(Org.id))).scalar_one()
    user_id = (
        await conn.execute(insert(User).values(org_id=org_id, email=email, name=name, role="admin").returning(User.id))
    ).scalar_one()
    await conn.execute(update(Org).where(Org.id == org_id).values(admin_user_id=user_id))
    return user_id
