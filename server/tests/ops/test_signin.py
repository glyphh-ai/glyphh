"""Signing in: found by the provider's id, linked by verified email, or new with a Free org of their own."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Forbidden
from glyphh_server.models import Identity, Org, User
from glyphh_server.ops.auth.signin import ProviderProfile, sign_in
from tests.db.helpers import an_email, person


def _profile(email: str, subject: str, provider: str = "google", verified: bool = True) -> ProviderProfile:
    return ProviderProfile(provider=provider, subject=subject, email=email, email_verified=verified, name=None)


async def test_a_new_person_gets_a_free_org_named_for_them_and_returns_by_their_id(engine: AsyncEngine) -> None:
    email = an_email()
    async with engine.begin() as conn:
        user_id = await sign_in(conn, _profile(email.upper(), f"g-{email}"))
        again = await sign_in(conn, _profile("changed@people.test", f"g-{email}"))
        both = select(User.email, User.role, Org.name, Org.admin_user_id).join(Org, Org.id == User.org_id)
        row = (await conn.execute(both)).all()
    assert again == user_id
    assert (email, "admin", f"{email.split('@')[0]}'s org", user_id) in [tuple(r) for r in row]


async def test_a_second_provider_with_the_same_verified_email_is_linked(engine: AsyncEngine) -> None:
    ada = await person(engine)
    async with engine.begin() as conn:
        assert await sign_in(conn, _profile(ada.email, f"gh-{ada.email}", "github")) == ada.user_id
        found = select(Identity.provider).where(Identity.user_id == ada.user_id)
        assert list((await conn.execute(found)).scalars()) == ["github"]


async def test_an_unverified_email_is_refused(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        with pytest.raises(Forbidden) as refused:
            await sign_in(conn, _profile(an_email(), "g-unverified", verified=False))
    assert refused.value.detail["reason"] == "unverified"
