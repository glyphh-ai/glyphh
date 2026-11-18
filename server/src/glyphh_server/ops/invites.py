"""Invites into an org by email, as the retired products left them: nothing makes one any more, but one still open
is honoured at its person's first sign-in (ops/auth/signin.py), who then joins that org instead of getting their
own."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Invite


def is_open():  # type: ignore[no-untyped-def]
    return (Invite.accepted_at.is_(None), Invite.expires_at > func.now())


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
