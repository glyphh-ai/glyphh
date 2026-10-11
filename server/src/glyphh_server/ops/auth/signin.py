"""Signing in with Google or GitHub. A person is found by the provider's own id for them; the first time,
by their verified email (linking the account) or, new to Glyphh, as a new member of a new org on Free.
Two first sign-ins at the same moment become one person: both wait on the same database lock."""

import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Forbidden
from glyphh_server.models import Org, Plan, SignInIdentity, User
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.auth")

NEW_ORG_PLAN: str = "Free"


class ProviderProfile(BaseModel):
    """What a provider tells us about the person, after their sign-in there."""

    provider: Literal["google", "github"]
    subject: str = Field(min_length=1)
    email: str = Field(min_length=3)
    email_verified: bool
    first_name: str | None = None
    last_name: str | None = None
    image_url: str | None = None


async def sign_in(conn: AsyncConnection, profile: ProviderProfile) -> uuid.UUID:
    if not profile.email_verified:
        raise Forbidden("Sign in with an account whose email is verified.", provider=profile.provider)
    email = profile.email.strip().lower()
    await _lock(conn, f"email:{email}")
    await _lock(conn, f"{profile.provider}:{profile.subject}")
    user_id = await _by_identity(conn, profile, email)
    how = "returning"
    if user_id is None:
        user_id, how = await _by_email(conn, email), "linked"
        if user_id is None:
            user_id, how = await _new_member(conn, profile, email), "new"
        await conn.execute(
            insert(SignInIdentity).values(
                user_id=user_id,
                provider=profile.provider,
                subject=profile.subject,
                email=email,
                last_used_at=datetime.now(UTC),
            )
        )
    if (await conn.execute(select(User.disabled_at).where(User.id == user_id))).scalar_one() is not None:
        raise Forbidden("Your account in this org is disabled. Ask an org admin.", provider=profile.provider)
    log.info("signed in", extra=fields(user=str(user_id), provider=profile.provider, how=how))
    return user_id


async def _lock(conn: AsyncConnection, key: str) -> None:
    await conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": key})


async def _by_identity(conn: AsyncConnection, profile: ProviderProfile, email: str) -> uuid.UUID | None:
    return (
        await conn.execute(
            update(SignInIdentity)
            .where(SignInIdentity.provider == profile.provider, SignInIdentity.subject == profile.subject)
            .values(email=email, last_used_at=datetime.now(UTC))
            .returning(SignInIdentity.user_id)
        )
    ).scalar_one_or_none()


async def _by_email(conn: AsyncConnection, email: str) -> uuid.UUID | None:
    return (await conn.execute(select(User.id).where(func.lower(User.email) == email))).scalar_one_or_none()


async def _new_member(conn: AsyncConnection, profile: ProviderProfile, email: str) -> uuid.UUID:
    """A new org on Free, under Glyphh, with this person as its admin."""
    plan_id = (await conn.execute(select(Plan.id).where(Plan.name == NEW_ORG_PLAN))).scalar_one()
    parent_id = (await conn.execute(select(Org.id).where(Org.parent_id.is_(None)))).scalar_one()
    name = f"{profile.first_name}'s org" if profile.first_name else email.split("@")[0]
    org_id = (
        await conn.execute(insert(Org).values(name=name, plan_id=plan_id, parent_id=parent_id).returning(Org.id))
    ).scalar_one()
    return (
        await conn.execute(
            insert(User)
            .values(
                org_id=org_id,
                role="org_admin",
                email=email,
                first_name=profile.first_name,
                last_name=profile.last_name,
                image_url=profile.image_url,
            )
            .returning(User.id)
        )
    ).scalar_one()
