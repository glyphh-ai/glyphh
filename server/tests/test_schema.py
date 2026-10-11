import uuid

import pytest
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server import schema
from glyphh_server.config import get_settings
from glyphh_server.models import Org, Token, User
from glyphh_server.schema import PARENT_ORG, apply_schema


async def _parent(engine: AsyncEngine) -> uuid.UUID:
    async with engine.connect() as conn:
        return (await conn.execute(select(Org.id).where(Org.parent_id.is_(None)))).scalar_one()


async def _org(engine: AsyncEngine, name: str) -> uuid.UUID:
    async with engine.begin() as conn:
        return (
            await conn.execute(insert(Org).values(name=name, parent_id=await _parent(engine)).returning(Org.id))
        ).scalar_one()


async def _user(engine: AsyncEngine, org_id: uuid.UUID, email: str, role: str = "user") -> uuid.UUID:
    async with engine.begin() as conn:
        return (
            await conn.execute(
                insert(User)
                .values(org_id=org_id, role=role, email=email, first_name="Ada", last_name="Lovelace")
                .returning(User.id)
            )
        ).scalar_one()


async def test_glyphh_is_the_one_parent_org_even_after_rerunning(engine: AsyncEngine) -> None:
    await apply_schema(engine)
    async with engine.connect() as conn:
        roots = (await conn.execute(select(Org.name).where(Org.parent_id.is_(None)))).scalars().all()
    assert roots == [PARENT_ORG]


async def test_a_second_parent_org_is_refused(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError, match="orgs_one_parent"):
        async with engine.begin() as conn:
            await conn.execute(insert(Org).values(name="Another root"))


async def test_ids_are_guids_made_by_the_database(engine: AsyncEngine) -> None:
    org_id = await _org(engine, "Acme")
    assert isinstance(org_id, uuid.UUID) and org_id.version == 4


async def test_a_role_must_be_one_of_the_three(engine: AsyncEngine) -> None:
    org_id = await _org(engine, "Roles Inc")
    for role in ("super_admin", "org_admin", "user"):
        await _user(engine, org_id, f"{role}@roles.test", role)
    with pytest.raises(IntegrityError, match="users_role"):
        await _user(engine, org_id, "owner@roles.test", "owner")


async def test_an_email_belongs_to_one_user_whatever_its_case(engine: AsyncEngine) -> None:
    org_id = await _org(engine, "Case Co")
    await _user(engine, org_id, "Dana@Case.test")
    with pytest.raises(IntegrityError, match="users_email"):
        await _user(engine, org_id, "dana@case.TEST")


async def test_a_user_needs_an_org_and_an_org_with_users_stays(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError):
        await _user(engine, uuid.uuid4(), "orphan@nowhere.test")
    org_id = await _org(engine, "Kept Ltd")
    await _user(engine, org_id, "kept@kept.test")
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(delete(Org).where(Org.id == org_id))


async def test_a_users_tokens_go_with_the_user(engine: AsyncEngine) -> None:
    user_id = await _user(engine, await _org(engine, "Tokens Ltd"), "t@tokens.test")
    async with engine.begin() as conn:
        await conn.execute(
            insert(Token).values(
                user_id=user_id,
                access_hash="a" * 64,
                refresh_hash="r" * 64,
                access_expires_at=func.now(),
                refresh_expires_at=func.now(),
            )
        )
        await conn.execute(delete(User).where(User.id == user_id))
        left = (await conn.execute(select(func.count()).select_from(Token).where(Token.user_id == user_id))).scalar()
    assert left == 0


async def test_updating_a_user_moves_updated_at(engine: AsyncEngine) -> None:
    user_id = await _user(engine, await _org(engine, "Profile Co"), "p@profile.test")
    async with engine.begin() as conn:
        await conn.execute(update(User).where(User.id == user_id).values(first_name="Grace"))
    async with engine.connect() as conn:
        row = (
            await conn.execute(select(User.created_at, User.updated_at, User.first_name).where(User.id == user_id))
        ).one()
    assert row.first_name == "Grace" and row.updated_at > row.created_at


async def test_the_schema_step_runs_from_the_environment(engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLYPHH_DATABASE_URL", str(engine.url.render_as_string(hide_password=False)))
    get_settings.cache_clear()
    try:
        await schema.main()
    finally:
        get_settings.cache_clear()
    assert await _parent(engine)


def test_the_schema_step_runs_as_a_program(engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    import runpy
    import sys

    monkeypatch.delitem(sys.modules, "glyphh_server.schema")
    monkeypatch.setenv("GLYPHH_DATABASE_URL", str(engine.url.render_as_string(hide_password=False)))
    get_settings.cache_clear()
    try:
        runpy.run_module("glyphh_server.schema", run_name="__main__")
    finally:
        get_settings.cache_clear()
