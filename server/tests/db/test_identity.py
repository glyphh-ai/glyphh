import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import SignInIdentity, User
from tests.db.helpers import make_org, make_user


async def _identity(engine: AsyncEngine, user_id, provider: str, subject: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            insert(SignInIdentity).values(user_id=user_id, provider=provider, subject=subject, email="a@id.test")
        )


async def test_a_provider_account_belongs_to_one_user(engine: AsyncEngine) -> None:
    org = await make_org(engine, "Identity Co")
    ada, bob = await make_user(engine, org, "ada@id.test"), await make_user(engine, org, "bob@id.test")
    await _identity(engine, ada, "google", "g-100")
    await _identity(engine, ada, "github", "g-100")
    with pytest.raises(IntegrityError, match="sign_in_identities_subject"):
        await _identity(engine, bob, "google", "g-100")


async def test_only_google_and_github(engine: AsyncEngine) -> None:
    user = await make_user(engine, await make_org(engine, "Providers Co"), "p@id.test")
    with pytest.raises(IntegrityError, match="sign_in_identities_provider"):
        await _identity(engine, user, "microsoft", "m-1")


async def test_identities_go_with_their_user(engine: AsyncEngine) -> None:
    user = await make_user(engine, await make_org(engine, "Gone Co"), "gone@id.test")
    await _identity(engine, user, "github", "gh-gone")
    async with engine.begin() as conn:
        await conn.execute(delete(User).where(User.id == user))
        left = (
            await conn.execute(
                select(func.count()).select_from(SignInIdentity).where(SignInIdentity.subject == "gh-gone")
            )
        ).scalar()
    assert left == 0
