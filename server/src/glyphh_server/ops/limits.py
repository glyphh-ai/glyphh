"""Counting and locking for what an org holds. Plans are flat per org: members, installs and runtimes are unlimited
on every plan; a plan's runtime nodes and precedents per node are signed into its licence key and enforced by rrotor
(ops/license_keys.py). Callers lock the row a count belongs to first, so requests at the same moment are taken one
after another."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Org, User


async def lock_org(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    await conn.execute(select(Org.id).where(Org.id == org_id).with_for_update())


async def lock_user(conn: AsyncConnection, user_id: uuid.UUID) -> None:
    await conn.execute(select(User.id).where(User.id == user_id).with_for_update())


async def _count(conn: AsyncConnection, *where: object) -> int:
    return int((await conn.execute(select(func.count()).where(*where))).scalar_one())


async def members(conn: AsyncConnection, org_id: uuid.UUID) -> int:
    return await _count(conn, User.org_id == org_id)
