"""Inviting people into an org by email. An invite's link carries a token (only its hash is kept) and expires; members
are unlimited on every plan. A new person signing in
with the invite's email joins; someone already using Glyphh accepts with the token."""

import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import Invite, User
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from glyphh_server.ops.guards import require_admin, taken

INVITE_TTL: timedelta = timedelta(days=7)


class InviteView(BaseModel):
    id: uuid.UUID
    email: str
    expires_at: datetime
    created_at: datetime


def is_open():  # type: ignore[no-untyped-def]
    return (Invite.accepted_at.is_(None), Invite.expires_at > func.now())


async def create_invite(conn: AsyncConnection, who: Principal, email: str) -> tuple[InviteView, str]:
    """The invite, and its token: shown once, in the link, never stored."""
    require_admin(who)
    email = email.strip().lower()
    member = select(User.id).where(User.org_id == who.org_id, func.lower(User.email) == email)
    if (await conn.execute(member)).first() is not None:
        raise Conflict("That person is already in your org.", email=email)
    await conn.execute(
        delete(Invite).where(
            Invite.org_id == who.org_id,
            func.lower(Invite.email) == email,
            Invite.accepted_at.is_(None),
            Invite.expires_at <= func.now(),
        )
    )
    token = make_secret()
    with taken("That email already has an open invite.", email=email):
        row = (
            await conn.execute(
                insert(Invite)
                .values(
                    org_id=who.org_id,
                    email=email,
                    token_hash=hash_secret(token),
                    expires_at=datetime.now(UTC) + INVITE_TTL,
                )
                .returning(Invite.id, Invite.email, Invite.expires_at, Invite.created_at)
            )
        ).one()
    return InviteView(**row._mapping), token


async def list_invites(conn: AsyncConnection, who: Principal) -> list[InviteView]:
    rows = await conn.execute(
        select(Invite.id, Invite.email, Invite.expires_at, Invite.created_at)
        .where(Invite.org_id == who.org_id, *is_open())
        .order_by(Invite.created_at)
    )
    return [InviteView(**r._mapping) for r in rows]


async def revoke_invite(conn: AsyncConnection, who: Principal, invite_id: uuid.UUID) -> None:
    require_admin(who)
    gone = await conn.execute(
        delete(Invite).where(Invite.id == invite_id, Invite.org_id == who.org_id, Invite.accepted_at.is_(None))
    )
    if gone.rowcount == 0:
        raise NotFound("That invite isn't open in your org.", invite_id=str(invite_id))


async def take_waiting_invite(conn: AsyncConnection, email: str) -> uuid.UUID | None:
    """A new person's open invite, newest first: accepted now, answering its org."""
    waiting = (
        select(Invite.id)
        .where(func.lower(Invite.email) == email, *is_open())
        .order_by(Invite.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    return (
        await conn.execute(
            update(Invite).where(Invite.id == waiting).values(accepted_at=func.now()).returning(Invite.org_id)
        )
    ).scalar_one_or_none()
