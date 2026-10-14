"""Someone already using Glyphh joins the org that invited them. Only when their own org has no one else and
nothing paid: that org is then removed, so everyone stays in exactly one."""

import uuid

from pydantic import BaseModel
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, Forbidden, Invalid
from glyphh_server.models import Invite, Org, User
from glyphh_server.ops import limits
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret
from glyphh_server.ops.invites import is_open

EXPIRED: str = "This invite has expired, was used, or was revoked. Ask for a new one."


class Joined(BaseModel):
    org_id: uuid.UUID
    org: str


async def accept_invite(conn: AsyncConnection, who: Principal, token: str) -> Joined:
    await tenancy.leave(conn)  # the invite is another org's
    invite = (
        await conn.execute(
            select(Invite.id, Invite.org_id, Invite.email, Org.name)
            .join(Org, Org.id == Invite.org_id)
            .where(Invite.token_hash == hash_secret(token), *is_open())
            .with_for_update(of=Invite)
        )
    ).first()
    if invite is None:
        raise Invalid(EXPIRED, reason="invite_expired")
    email = (await conn.execute(select(User.email).where(User.id == who.user_id))).scalar_one()
    if email.lower() != invite.email.lower():
        raise Forbidden(f"This invite is for {invite.email}. Sign in with that account.", reason="wrong_account")
    if invite.org_id == who.org_id:
        raise Conflict("You're already in that org.")
    await _leavable(conn, who.org_id)
    await conn.execute(update(Invite).where(Invite.id == invite.id).values(accepted_at=func.now()))
    await conn.execute(update(User).where(User.id == who.user_id).values(org_id=invite.org_id, role="member"))
    await conn.execute(delete(Invite).where(Invite.org_id == who.org_id))
    await conn.execute(delete(Org).where(Org.id == who.org_id))
    return Joined(org_id=invite.org_id, org=invite.name)


async def _leavable(conn: AsyncConnection, org_id: uuid.UUID) -> None:
    await limits.lock_org(conn, org_id)
    paid = (await conn.execute(select(Org.stripe_subscription_id).where(Org.id == org_id))).scalar_one()
    if await limits.members(conn, org_id) > 1 or paid is not None:
        raise Conflict(
            "You can join only from an org of your own with no one else in it and nothing paid.", reason="not_alone"
        )
