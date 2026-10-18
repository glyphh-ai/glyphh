"""The person's side of the device flow: the sign-in waiting for them by its code, then approve or deny. Approving
on a machine the person already has reuses its install (its old tokens revoked); a new machine is a new install,
never limited."""

import uuid

from pydantic import BaseModel
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid
from glyphh_server.models import DeviceCode, Install
from glyphh_server.ops import limits
from glyphh_server.ops.auth.tokens import revoke_tokens
from glyphh_server.ops.device import normalize

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
    install_id = await _reuse(conn, user_id, found) or await _new_install(conn, user_id, found)
    await conn.execute(
        update(DeviceCode)
        .where(DeviceCode.device_code_hash == found.device_code_hash)
        .values(install_id=install_id, approved_at=func.now())
    )
    return WaitingSignIn(user_code=found.user_code, name=found.name, surface=found.surface)


async def _reuse(conn: AsyncConnection, user_id: uuid.UUID, found: DeviceCode) -> uuid.UUID | None:
    """The person's install on this machine, if they have one: its old tokens revoked, refreshed from the code."""
    install_id = (
        await conn.execute(
            select(Install.id).where(
                Install.user_id == user_id, Install.machine_id == found.machine_id, Install.revoked_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if install_id is None:
        return None
    await revoke_tokens(conn, install_id)
    await conn.execute(
        update(Install)
        .where(Install.id == install_id)
        .values(name=found.name, surface=found.surface, mod_version=found.mod_version, last_seen_at=func.now())
    )
    return install_id


async def _new_install(conn: AsyncConnection, user_id: uuid.UUID, found: DeviceCode) -> uuid.UUID:
    """A machine the person has not signed in on: a new install. Installs are unlimited on every plan."""
    values = {
        "user_id": user_id,
        "machine_id": found.machine_id,
        "name": found.name,
        "surface": found.surface,
        "mod_version": found.mod_version,
    }
    return (await conn.execute(insert(Install).values(values).returning(Install.id))).scalar_one()


async def deny(conn: AsyncConnection, user_code: str) -> None:
    denied = await conn.execute(update(DeviceCode).where(*_waiting(user_code)).values(denied_at=func.now()))
    if denied.rowcount == 0:
        raise Invalid(GONE, reason="code")
