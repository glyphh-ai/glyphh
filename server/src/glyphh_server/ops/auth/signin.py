"""Signing in with Google or GitHub. A person is found by the provider's own id for them; the first time, by their
verified email (linking the account), or, new to Glyphh, as a new person: into the org whose invite for their email
is waiting, or else into a new Free org of their own, as its admin. Two first sign-ins at the same moment become one
person: both wait on the same database lock. A person whose org enforces single sign-on (ops/sso.py) is refused
here and sent to it.

Signing in with an org's single sign-on (`sso`, the org named by the profile): found by the provider's id, else by
email, and in either case they must be that org's, or new to Glyphh: then a member of that org (its open invite
for them, if any, accepted). Nobody is moved between orgs, and nobody gets an org of their own, by SSO."""

import logging
import uuid
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Forbidden
from glyphh_server.models import Identity, Invite, OrgSso, User
from glyphh_server.obs.logs import fields
from glyphh_server.ops.invites import is_open, take_waiting_invite
from glyphh_server.ops.orgs import new_person

log = logging.getLogger("glyphh.auth")

SSO: str = "sso"
SSO_REQUIRED: str = "Your organisation signs in with single sign-on: go back and continue with it."
OTHER_ORG: str = (
    "This account belongs to another Glyphh organisation. Sign in there, accept your organisation's invite, then "
    "use single sign-on."
)


class ProviderProfile(BaseModel):
    """What a provider tells us about the person, after their sign-in there."""

    provider: Literal["google", "github", "sso"]
    subject: str = Field(min_length=1)
    email: str = Field(min_length=3)
    email_verified: bool
    name: str | None = None
    org_id: uuid.UUID | None = None  # a single sign-on's org: the person lands there and nowhere else
    groups: list[str] = []  # a single sign-on's groups claim, the person's roles (docs/specs/apps.md, 2)


async def sign_in(conn: AsyncConnection, profile: ProviderProfile) -> uuid.UUID:
    if not profile.email_verified:
        raise Forbidden(
            "Sign in with an account whose email is verified.",
            provider=profile.provider,
            reason="unverified",
            email=profile.email,
        )
    if profile.provider == SSO:
        return await _sign_in_sso(conn, profile)
    email = profile.email.strip().lower()
    await lock(conn, f"email:{email}")
    await lock(conn, f"{profile.provider}:{profile.subject}")
    user_id, how = await _by_identity(conn, profile), "returning"
    if user_id is None:
        user_id, how = await _by_email(conn, email), "linked"
    if user_id is not None and await _sso_enforced(conn, user_id):
        raise Forbidden(SSO_REQUIRED, provider=profile.provider, reason="sso_required")
    if how != "returning":
        if user_id is None:
            user_id, how = await _new_user(conn, email, profile.name), "new"
        await conn.execute(
            insert(Identity).values(user_id=user_id, provider=profile.provider, provider_user_id=profile.subject)
        )
    log.info("signed in", extra=fields(user=str(user_id), provider=profile.provider, how=how))
    return user_id


async def _sign_in_sso(conn: AsyncConnection, profile: ProviderProfile) -> uuid.UUID:
    org_id = profile.org_id
    assert org_id is not None  # an SSO profile names its org (ops/auth/providers/oidc.py)
    email = profile.email.strip().lower()
    await lock(conn, f"email:{email}")
    await lock(conn, f"{SSO}:{profile.subject}")
    found = (
        await conn.execute(
            select(User.id, User.org_id)
            .join(Identity, Identity.user_id == User.id)
            .where(Identity.provider == SSO, Identity.provider_user_id == profile.subject)
        )
    ).first()
    how = "returning"
    if found is None:
        found = (await conn.execute(select(User.id, User.org_id).where(func.lower(User.email) == email))).first()
        how = "linked" if found is not None else "new"
    if found is not None and found.org_id != org_id:
        raise Forbidden(OTHER_ORG, provider=SSO, reason="other_org")
    if found is None:
        values = {"org_id": org_id, "email": email, "name": profile.name, "role": "member", "groups": profile.groups}
        user_id = (await conn.execute(insert(User).values(**values).returning(User.id))).scalar_one()
        waiting = update(Invite).where(Invite.org_id == org_id, func.lower(Invite.email) == email, *is_open())
        await conn.execute(waiting.values(accepted_at=func.now()))
    else:
        user_id = found.id
        await conn.execute(update(User).where(User.id == user_id).values(groups=profile.groups))
    if how != "returning":
        await conn.execute(insert(Identity).values(user_id=user_id, provider=SSO, provider_user_id=profile.subject))
    log.info("signed in", extra=fields(user=str(user_id), provider=SSO, how=how, org=str(org_id)))
    return user_id


async def _sso_enforced(conn: AsyncConnection, user_id: uuid.UUID) -> bool:
    """Whether this person's org makes its people sign in with single sign-on."""
    enforced = select(OrgSso.enforced).join(User, User.org_id == OrgSso.org_id).where(User.id == user_id).limit(1)
    return bool((await conn.execute(enforced)).scalar_one_or_none())


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
