"""The people in an org. Org admins change roles, disable and remove; nobody changes their own access,
and an org always keeps at least one active org admin."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Forbidden, NotFound
from glyphh_server.models import Membership, User
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.guards import refusals, require_admin

MemberRole = Literal["org_admin", "user"]
_COLUMNS = (
    User.id,
    User.email,
    User.first_name,
    User.last_name,
    Membership.role,
    Membership.disabled_at,
    Membership.created_at,
)


def _in_org(org_id: uuid.UUID):  # type: ignore[no-untyped-def]
    return select(*_COLUMNS).join(Membership, Membership.user_id == User.id).where(Membership.org_id == org_id)


class Member(BaseModel):
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    disabled: bool
    joined_at: datetime


def _member(row: object) -> Member:
    r = row._mapping  # type: ignore[attr-defined]
    return Member(
        id=r["id"],
        email=r["email"],
        first_name=r["first_name"],
        last_name=r["last_name"],
        role=r["role"],
        disabled=r["disabled_at"] is not None,
        joined_at=r["created_at"],
    )


async def list_members(conn: AsyncConnection, who: Principal) -> list[Member]:
    rows = await conn.execute(_in_org(who.org_id).order_by(Membership.created_at))
    return [_member(r) for r in rows]


async def _target(conn: AsyncConnection, who: Principal, member_id: uuid.UUID) -> object:
    require_admin(who)
    if member_id == who.user_id:
        raise Forbidden("You can't change your own access. Ask another org admin.")
    row = (await conn.execute(_in_org(who.org_id).where(User.id == member_id))).first()
    if row is None:
        raise NotFound("That person isn't in your org.", member_id=str(member_id))
    if row.role == "super_admin":
        raise Forbidden("Super admins are managed by Glyphh, not from an org.")
    return row


async def _keep_an_admin(conn: AsyncConnection, who: Principal, member_id: uuid.UUID) -> None:
    others = (
        select(func.count())
        .select_from(Membership)
        .where(
            Membership.org_id == who.org_id,
            Membership.role == "org_admin",
            Membership.disabled_at.is_(None),
            Membership.user_id != member_id,
        )
    )
    if (await conn.execute(others)).scalar_one() == 0:
        raise Conflict("Your org needs at least one active org admin.")


async def update_member(
    conn: AsyncConnection,
    who: Principal,
    member_id: uuid.UUID,
    role: MemberRole | None = None,
    disabled: bool | None = None,
) -> Member:
    current = _member(await _target(conn, who, member_id))
    if current.role == "org_admin" and (role == "user" or disabled):
        await _keep_an_admin(conn, who, member_id)
    values: dict[str, object] = {}
    if role is not None:
        values["role"] = role
    if disabled is not None:
        values["disabled_at"] = func.now() if disabled else None
    if values:
        with refusals("That change clashes with another member."):
            await conn.execute(update(Membership).where(*_this(who, member_id)).values(**values))
    return _member((await conn.execute(_in_org(who.org_id).where(User.id == member_id))).one())


async def remove_member(conn: AsyncConnection, who: Principal, member_id: uuid.UUID) -> None:
    current = _member(await _target(conn, who, member_id))
    if current.role == "org_admin":
        await _keep_an_admin(conn, who, member_id)
    await conn.execute(delete(Membership).where(*_this(who, member_id)))


def _this(who: Principal, member_id: uuid.UUID) -> tuple[object, object]:
    """The member's membership in the caller's org: an org admin reaches only their own org's."""
    return (Membership.user_id == member_id, Membership.org_id == who.org_id)
