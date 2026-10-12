"""Inviting people into an org by email. An invite's link carries a token (only its hash is kept) and
expires; an open invite holds a seat. Accepting it, as that email, makes the person a member."""

import uuid
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Conflict, Forbidden, Invalid, NotFound
from glyphh_server.models import Invite, Membership, Org, User
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from glyphh_server.ops.guards import refusals, require_admin
from glyphh_server.ops.members import MemberRole

INVITE_TTL: timedelta = timedelta(days=7)


class InviteView(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime


class OpenInvite(BaseModel):
    """What the Join page shows before the person signs in."""

    org: str
    email: str
    role: str
    invited_by: str | None = None
    invited_by_email: str | None = None
    expires_at: datetime


def _open():
    return (
        Invite.accepted_at.is_(None),
        Invite.declined_at.is_(None),
        Invite.revoked_at.is_(None),
        Invite.expires_at > func.now(),
    )


async def create_invite(conn: AsyncConnection, who: Principal, email: str, role: MemberRole) -> tuple[InviteView, str]:
    """The invite, and its token: shown once, in the link, never stored."""
    require_admin(who)
    email = email.strip().lower()
    if (await conn.execute(select(Org.personal_user_id).where(Org.id == who.org_id))).scalar_one() is not None:
        raise Forbidden("A Personal org is yours alone. Invite people into an org you share.", reason="personal")
    member = (
        select(Membership.user_id)
        .join(User, User.id == Membership.user_id)
        .where(Membership.org_id == who.org_id, func.lower(User.email) == email)
    )
    if (await conn.execute(member)).first() is not None:
        raise Conflict("That person is already in your org.", email=email)
    token = make_secret()
    with refusals("That email already has an open invite."):
        row = (
            await conn.execute(
                insert(Invite)
                .values(
                    org_id=who.org_id,
                    email=email,
                    role=role,
                    invited_by=who.user_id,
                    token_hash=hash_secret(token),
                    expires_at=datetime.now(UTC) + INVITE_TTL,
                )
                .returning(Invite.id, Invite.email, Invite.role, Invite.expires_at)
            )
        ).one()
    return InviteView(id=row.id, email=row.email, role=row.role, expires_at=row.expires_at), token


async def list_invites(conn: AsyncConnection, who: Principal) -> list[InviteView]:
    require_admin(who)
    rows = await conn.execute(
        select(Invite.id, Invite.email, Invite.role, Invite.expires_at)
        .where(Invite.org_id == who.org_id, *_open())
        .order_by(Invite.created_at)
    )
    return [InviteView(id=r.id, email=r.email, role=r.role, expires_at=r.expires_at) for r in rows]


async def revoke_invite(conn: AsyncConnection, who: Principal, invite_id: uuid.UUID) -> None:
    require_admin(who)
    ended = await conn.execute(
        update(Invite)
        .where(Invite.id == invite_id, Invite.org_id == who.org_id, *_open())
        .values(revoked_at=func.now())
    )
    if ended.rowcount == 0:
        raise NotFound("That invite isn't open in your org.", invite_id=str(invite_id))


async def read_invite(conn: AsyncConnection, token: str) -> OpenInvite:
    row = (
        await conn.execute(
            select(
                Org.name,
                Invite.email,
                Invite.role,
                Invite.expires_at,
                User.first_name,
                User.last_name,
                User.email.label("by_email"),
            )
            .join(Org, Org.id == Invite.org_id)
            .outerjoin(User, User.id == Invite.invited_by)
            .where(Invite.token_hash == hash_secret(token), *_open())
        )
    ).first()
    if row is None:
        raise Invalid(
            "This invite has expired, was used, or was withdrawn. Ask for a new one.", reason="invite_expired"
        )
    by = " ".join(n for n in (row.first_name, row.last_name) if n) or row.by_email
    return OpenInvite(
        org=row.name,
        email=row.email,
        role=row.role,
        invited_by=by,
        invited_by_email=row.by_email,
        expires_at=row.expires_at,
    )


def _wrong(invite: OpenInvite, email: str) -> Forbidden:
    return Forbidden(
        f"This invite is for {invite.email}. Sign in with that account.",
        reason="wrong_account",
        invited=invite.email,
        email=email,
    )


async def _person(conn: AsyncConnection, user_id: uuid.UUID) -> str:
    return (await conn.execute(select(User.email).where(User.id == user_id))).scalar_one()


async def accept_invite(conn: AsyncConnection, token: str, user_id: uuid.UUID) -> str:
    """Add the person to the invite's org, as the invite's email only; they keep every other org. Answers its name."""
    invite = await read_invite(conn, token)
    email = await _person(conn, user_id)
    if email.strip().lower() != invite.email:
        raise _wrong(invite, email)
    row = (
        await conn.execute(
            update(Invite)
            .where(Invite.token_hash == hash_secret(token), *_open())
            .values(accepted_at=func.now())
            .returning(Invite.org_id, Invite.role)
        )
    ).first()
    if row is None:
        raise Invalid(
            "This invite has expired, was used, or was withdrawn. Ask for a new one.", reason="invite_expired"
        )
    with refusals("You're already in that org."):
        await conn.execute(insert(Membership).values(user_id=user_id, org_id=row.org_id, role=row.role))
    return invite.org


async def decline_invite(conn: AsyncConnection, token: str, user_id: uuid.UUID) -> None:
    """The invited person says no: the invite closes and its seat is free again."""
    invite = await read_invite(conn, token)
    email = await _person(conn, user_id)
    if email.strip().lower() != invite.email:
        raise _wrong(invite, email)
    await conn.execute(
        update(Invite).where(Invite.token_hash == hash_secret(token), *_open()).values(declined_at=func.now())
    )
