"""Signing in: found by the provider's id, linked by verified email, or new: into the org whose invite is waiting for
their email, else with a Free org of their own."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Forbidden
from glyphh_server.models import Identity, Invite, Org, User
from glyphh_server.ops.auth.signin import ProviderProfile, sign_in
from glyphh_server.ops.orgs import org_name
from tests.db.helpers import an_email, person, plan_version

DAY: timedelta = timedelta(days=1)


def _profile(email: str, subject: str, provider: str = "google", verified: bool = True) -> ProviderProfile:
    return ProviderProfile(provider=provider, subject=subject, email=email, email_verified=verified, name=None)


async def _invited(
    engine: AsyncEngine, org_id: uuid.UUID, email: str, expires: timedelta = DAY, **over: object
) -> uuid.UUID:
    """An invite into this org, as the retired products left them."""
    values = {"org_id": org_id, "email": email, "token_hash": uuid.uuid4().hex, **over}
    async with engine.begin() as conn:
        made = insert(Invite).values(**values, expires_at=datetime.now(UTC) + expires).returning(Invite.id)
        return (await conn.execute(made)).scalar_one()


async def _user(engine: AsyncEngine, user_id: uuid.UUID) -> tuple[uuid.UUID, str, str]:
    async with engine.connect() as conn:
        return tuple((await conn.execute(select(User.org_id, User.role, User.email).where(User.id == user_id))).one())  # type: ignore[return-value]


async def test_a_new_person_gets_a_free_org_named_for_them_and_returns_by_their_id(engine: AsyncEngine) -> None:
    email = an_email()
    async with engine.begin() as conn:
        user_id = await sign_in(conn, _profile(f"  {email.upper()} ", f"g-{email}"))
        again = await sign_in(conn, _profile("changed@people.test", f"g-{email}"))
        both = select(User.email, User.role, Org.name, Org.admin_user_id, Org.plan_version_id)
        row = (await conn.execute(both.join(Org, Org.id == User.org_id).where(User.id == user_id))).one()
        free = await plan_version(conn, "Free")
    assert again == user_id
    assert tuple(row) == (email, "admin", f"{email.split('@')[0]}'s org", user_id, free)


def test_an_org_is_named_for_its_person_or_their_email() -> None:
    assert org_name("Ada Lovelace", "ada@people.test") == "Ada Lovelace's org"
    assert org_name(None, "ada@people.test") == org_name("", "ada@people.test") == "ada's org"


async def test_a_second_provider_with_the_same_verified_email_is_linked(engine: AsyncEngine) -> None:
    ada = await person(engine)
    async with engine.begin() as conn:
        assert await sign_in(conn, _profile(ada.email.upper(), f"gh-{ada.email}", "github")) == ada.user_id
        found = select(Identity.provider).where(Identity.user_id == ada.user_id)
        assert list((await conn.execute(found)).scalars()) == ["github"]
        assert await sign_in(conn, _profile(ada.email, f"gh-{ada.email}", "github")) == ada.user_id
        assert list((await conn.execute(found)).scalars()) == ["github"]


async def test_an_unverified_email_is_refused(engine: AsyncEngine) -> None:
    email = an_email()
    async with engine.begin() as conn:
        with pytest.raises(Forbidden) as refused:
            await sign_in(conn, _profile(email, "g-unverified", verified=False))
        assert (await conn.execute(select(User.id).where(User.email == email))).first() is None
    assert refused.value.detail == {"provider": "google", "reason": "unverified", "email": email}


async def test_a_new_person_with_an_invite_waiting_joins_its_org_as_a_member(engine: AsyncEngine) -> None:
    ada, email = await person(engine, "Team"), an_email()
    invite_id = await _invited(engine, ada.org_id, email.upper())
    async with engine.begin() as conn:
        user_id = await sign_in(conn, _profile(email, f"g-{email}"))
    assert await _user(engine, user_id) == (ada.org_id, "member", email)
    async with engine.connect() as conn:
        accepted = (await conn.execute(select(Invite.accepted_at).where(Invite.id == invite_id))).scalar_one()
        assert accepted is not None
        assert (await conn.execute(select(Org.admin_user_id).where(Org.id == ada.org_id))).scalar_one() == ada.user_id


async def test_the_newest_open_invite_is_the_one_taken_and_the_others_stay_open(engine: AsyncEngine) -> None:
    ada, eve, email = await person(engine), await person(engine), an_email()
    older = await _invited(engine, ada.org_id, email, created_at=datetime.now(UTC) - DAY)
    newer = await _invited(engine, eve.org_id, email)
    async with engine.begin() as conn:
        user_id = await sign_in(conn, _profile(email, f"g-{email}"))
    assert (await _user(engine, user_id))[0] == eve.org_id
    async with engine.connect() as conn:
        open_still = select(Invite.id).where(Invite.email == email, Invite.accepted_at.is_(None))
        assert list((await conn.execute(open_still)).scalars()) == [older] and older != newer


async def test_an_invite_expired_already_accepted_or_for_someone_else_is_not_taken(engine: AsyncEngine) -> None:
    ada, email = await person(engine), an_email()
    await _invited(engine, ada.org_id, email, expires=-DAY)
    await _invited(engine, ada.org_id, email, accepted_at=datetime.now(UTC))
    await _invited(engine, ada.org_id, an_email())
    async with engine.begin() as conn:
        user_id = await sign_in(conn, _profile(email, f"g-{email}"))
    org_id, role, _ = await _user(engine, user_id)
    assert org_id != ada.org_id and role == "admin"


async def test_someone_already_here_is_not_moved_by_an_invite(engine: AsyncEngine) -> None:
    ada, bob = await person(engine), await person(engine)
    invite_id = await _invited(engine, ada.org_id, bob.email)
    async with engine.begin() as conn:
        assert await sign_in(conn, _profile(bob.email, f"g-{bob.email}")) == bob.user_id
        assert (await conn.execute(select(Invite.accepted_at).where(Invite.id == invite_id))).scalar_one() is None
    assert (await _user(engine, bob.user_id))[0] == bob.org_id
