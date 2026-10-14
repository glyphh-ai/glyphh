"""Signing in with Google or GitHub. A person is found by the provider's own id for them; the first time, by their
verified email (linking the account), or, new to Glyphh, as a new person: into the org whose invite for their email
is waiting, or else into a new Free org of their own, as its admin. Two first sign-ins at the same moment become one
person: both wait on the same database lock."""

import logging
import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Forbidden
from glyphh_server.models import Identity, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops.invites import take_waiting_invite
from glyphh_server.ops.orgs import new_person

log = logging.getLogger("glyphh.auth")


class ProviderProfile(BaseModel):
    """What a provider tells us about the person, after their sign-in there."""

    provider: Literal["google", "github"]
    subject: str = Field(min_length=1)
    email: str = Field(min_length=3)
    email_verified: bool
    name: str | None = None


async def sign_in(conn: AsyncConnection, profile: ProviderProfile) -> uuid.UUID:
    if not profile.email_verified:
        raise Forbidden(
            "Sign in with an account whose email is verified.",
            provider=profile.provider,
            reason="unverified",
            email=profile.email,
        )
    email = profile.email.strip().lower()
    await lock(conn, f"email:{email}")
    await lock(conn, f"{profile.provider}:{profile.subject}")
    user_id, how = await _by_identity(conn, profile), "returning"
    if user_id is None:
        user_id, how = await _by_email(conn, email), "linked"
        if user_id is None:
            user_id, how = await _new_user(conn, email, profile.name), "new"
        await conn.execute(
            insert(Identity).values(user_id=user_id, provider=profile.provider, provider_user_id=profile.subject)
        )
    log.info("signed in", extra=fields(user=str(user_id), provider=profile.provider, how=how))
    return user_id


async def lock(conn: AsyncConnection, key: str) -> None:
    await conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": key})


async def _by_identity(conn: AsyncConnection, profile: ProviderProfile) -> uuid.UUID | None:
    found = select(Identity.user_id).where(
        Identity.provider == profile.provider, Identity.provider_user_id == profile.subject
    )
    return (await conn.execute(found)).scalar_one_or_none()


async def _by_email(conn: AsyncConnection, email: str) -> uuid.UUID | None:
    return (await conn.execute(select(User.id).where(func.lower(User.email) == email))).scalar_one_or_none()


async def _new_user(conn: AsyncConnection, email: str, name: str | None) -> uuid.UUID:
    org_id = await take_waiting_invite(conn, email)
    if org_id is None:
        return await new_person(conn, email, name)
    return (
        await conn.execute(insert(User).values(org_id=org_id, email=email, name=name, role="member").returning(User.id))
    ).scalar_one()
