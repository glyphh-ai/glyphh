"""The person's side of the device flow: the sign-in waiting for them by its code, then approve (making the
install, refused past the plan's max_installs) or deny."""

import uuid

from pydantic import BaseModel
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid
from glyphh_server.models import DeviceCode, Install, User
from glyphh_server.ops import limits
from glyphh_server.ops.device import normalize
from glyphh_server.ops.plans import org_version

GONE: str = "This code has expired, was used, or is not right. Start again in Claude."


class WaitingSignIn(BaseModel):
    user_code: str
    name: str
    surface: str


def _waiting(user_code: str):  # type: ignore[no-untyped-def]
    return (
        DeviceCode.user_code == normalize(user_code),
        DeviceCode.approved_at.is_(None),
        DeviceCode.denied_at.is_(None),
        DeviceCode.expires_at > func.now(),
    )


async def waiting(conn: AsyncConnection, user_code: str) -> WaitingSignIn:
    row = (
        await conn.execute(
            select(DeviceCode.user_code, DeviceCode.name, DeviceCode.surface).where(*_waiting(user_code))
        )
    ).first()
    if row is None:
        raise Invalid(GONE, reason="code")
    return WaitingSignIn(**row._mapping)


async def approve(conn: AsyncConnection, user_code: str, user_id: uuid.UUID) -> WaitingSignIn:
    code = (await conn.execute(select(DeviceCode).where(*_waiting(user_code)).with_for_update())).first()
    if code is None:
        raise Invalid(GONE, reason="code")
    found = DeviceCode(**code._mapping)
    await limits.lock_user(conn, user_id)
    org_id = (await conn.execute(select(User.org_id).where(User.id == user_id))).scalar_one()
    await limits.check(conn, "installs", await limits.installs(conn, user_id), await org_version(conn, org_id))
    install_id = (
        await conn.execute(
            insert(Install)
            .values(user_id=user_id, name=found.name, surface=found.surface, mod_version=found.mod_version)
            .returning(Install.id)
        )
    ).scalar_one()
    await conn.execute(
        update(DeviceCode)
        .where(DeviceCode.device_code_hash == found.device_code_hash)
        .values(install_id=install_id, approved_at=func.now())
    )
    return WaitingSignIn(user_code=found.user_code, name=found.name, surface=found.surface)


async def deny(conn: AsyncConnection, user_code: str) -> None:
    denied = await conn.execute(update(DeviceCode).where(*_waiting(user_code)).values(denied_at=func.now()))
    if denied.rowcount == 0:
        raise Invalid(GONE, reason="code")
