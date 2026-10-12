import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Forbidden
from glyphh_server.models import Org, SignInIdentity, User
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.signin import ProviderProfile, sign_in
from glyphh_server.ops.me import me
from tests.db.helpers import make_org, make_user


def _profile(subject: str, email: str, provider: str = "google", **extra: object) -> ProviderProfile:
    return ProviderProfile(provider=provider, subject=subject, email=email, email_verified=True, **extra)


async def _sign_in(engine: AsyncEngine, profile: ProviderProfile):
    async with engine.begin() as conn:
        return await sign_in(conn, profile)


async def _count(engine: AsyncEngine, table, *where) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(select(func.count()).select_from(table).where(*where))).scalar()


async def test_a_new_person_gets_a_new_org_on_free_as_its_admin(engine: AsyncEngine) -> None:
    user = await _sign_in(
        engine,
        _profile(
            "g-new", "New.Person@Example.test", first_name="Nia", last_name="Ng", image_url="https://img.test/n.png"
        ),
    )
    async with engine.connect() as conn:
        role, org_id = (await conn.execute(select(User.role, User.org_id).where(User.id == user))).one()
        mine = await me(conn, Principal(user_id=user, org_id=org_id, role=role))
    assert (mine.email, mine.first_name, mine.role) == ("new.person@example.test", "Nia", "org_admin")
    assert (mine.org.name, mine.org.plan) == ("Nia's org", "Free")


async def test_a_person_without_a_first_name_gets_an_org_named_from_their_email(engine: AsyncEngine) -> None:
    user = await _sign_in(engine, _profile("gh-anon", "octo@cat.test", provider="github"))
    async with engine.connect() as conn:
        name = (await conn.execute(select(Org.name).join(User, User.org_id == Org.id).where(User.id == user))).scalar()
    assert name == "octo"


async def test_signing_in_again_finds_the_same_person_even_with_a_new_email(engine: AsyncEngine) -> None:
    first = await _sign_in(engine, _profile("g-again", "again@one.test"))
    second = await _sign_in(engine, _profile("g-again", "renamed@two.test"))
    assert first == second
    assert (
        await _count(
            engine, SignInIdentity, SignInIdentity.subject == "g-again", SignInIdentity.email == "renamed@two.test"
        )
        == 1
    )


async def test_a_second_provider_with_the_same_verified_email_links_to_the_same_person(engine: AsyncEngine) -> None:
    google = await _sign_in(engine, _profile("g-both", "both@link.test"))
    github = await _sign_in(engine, _profile("gh-both", "Both@Link.test", provider="github"))
    assert google == github
    assert await _count(engine, SignInIdentity, SignInIdentity.user_id == google) == 2


async def test_an_invited_or_existing_member_is_linked_not_duplicated(engine: AsyncEngine) -> None:
    existing = await make_user(engine, await make_org(engine, "Existing Co"), "member@existing.test")
    assert await _sign_in(engine, _profile("g-member", "member@existing.test")) == existing


async def test_an_unverified_email_is_refused(engine: AsyncEngine) -> None:
    profile = ProviderProfile(provider="github", subject="gh-x", email="x@unverified.test", email_verified=False)
    with pytest.raises(Forbidden) as caught:
        await _sign_in(engine, profile)
    assert caught.value.detail == {"provider": "github", "reason": "unverified", "email": "x@unverified.test"}
    assert await _count(engine, User, func.lower(User.email) == "x@unverified.test") == 0


async def test_two_first_sign_ins_at_once_make_one_person_and_one_org(engine: AsyncEngine) -> None:
    profile = _profile("g-race", "race@once.test", first_name="Rae")
    results = await asyncio.gather(*(_sign_in(engine, profile) for _ in range(5)))
    assert len(set(results)) == 1
    assert await _count(engine, User, User.email == "race@once.test") == 1
    assert await _count(engine, Org, Org.name == "Rae's org") == 1


async def test_a_disabled_member_cannot_sign_in(engine: AsyncEngine) -> None:
    from sqlalchemy import update

    user = await _sign_in(engine, _profile("g-off", "off@disabled.test"))
    async with engine.begin() as conn:
        await conn.execute(update(User).where(User.id == user).values(disabled_at=func.now()))
    with pytest.raises(Forbidden, match="disabled"):
        await _sign_in(engine, _profile("g-off", "off@disabled.test"))
