import runpy
import sys
import uuid

import pytest
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import get_settings
from glyphh_server.db import schema
from glyphh_server.db.schema import apply_schema
from glyphh_server.db.seed import PARENT_ORG, PARENT_PLAN
from glyphh_server.models import Org, Plan, Token, User
from tests.conftest import SETTINGS
from tests.db.helpers import make_org, make_user, parent_id, plan_id


async def test_glyphh_is_the_one_parent_org_on_enterprise_even_after_rerunning(engine: AsyncEngine) -> None:
    await apply_schema(engine, SETTINGS)
    async with engine.connect() as conn:
        roots = (await conn.execute(select(Org.name, Org.plan_id).where(Org.parent_id.is_(None)))).all()
    assert roots == [(PARENT_ORG, await plan_id(engine, PARENT_PLAN))]


async def test_a_second_parent_org_is_refused(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError, match="orgs_one_parent"):
        async with engine.begin() as conn:
            await conn.execute(insert(Org).values(name="Another root", plan_id=await plan_id(engine)))


async def test_ids_are_guids_made_by_the_database(engine: AsyncEngine) -> None:
    org_id = await make_org(engine, "Acme")
    assert isinstance(org_id, uuid.UUID) and org_id.version == 4


async def test_an_org_needs_a_plan_and_a_plan_in_use_stays(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(
                insert(Org).values(name="No plan", parent_id=await parent_id(engine), plan_id=uuid.uuid4())
            )
    await make_org(engine, "On Pro", "Pro")
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(delete(Plan).where(Plan.name == "Pro"))


async def test_a_role_must_be_one_of_the_three(engine: AsyncEngine) -> None:
    org_id = await make_org(engine, "Roles Inc")
    for role in ("super_admin", "org_admin", "user"):
        await make_user(engine, org_id, f"{role}@roles.test", role)
    with pytest.raises(IntegrityError, match="users_role"):
        await make_user(engine, org_id, "owner@roles.test", "owner")


async def test_an_email_belongs_to_one_user_whatever_its_case(engine: AsyncEngine) -> None:
    org_id = await make_org(engine, "Case Co")
    await make_user(engine, org_id, "Dana@Case.test")
    with pytest.raises(IntegrityError, match="users_email"):
        await make_user(engine, org_id, "dana@case.TEST")


async def test_a_user_needs_an_org_and_an_org_with_users_stays(engine: AsyncEngine) -> None:
    with pytest.raises(IntegrityError):
        await make_user(engine, uuid.uuid4(), "orphan@nowhere.test")
    org_id = await make_org(engine, "Kept Ltd")
    await make_user(engine, org_id, "kept@kept.test")
    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await conn.execute(delete(Org).where(Org.id == org_id))


async def test_a_users_tokens_go_with_the_user(engine: AsyncEngine) -> None:
    user_id = await make_user(engine, await make_org(engine, "Tokens Ltd"), "t@tokens.test")
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
    user_id = await make_user(engine, await make_org(engine, "Profile Co"), "p@profile.test")
    async with engine.begin() as conn:
        await conn.execute(update(User).where(User.id == user_id).values(first_name="Grace"))
    async with engine.connect() as conn:
        row = (
            await conn.execute(select(User.created_at, User.updated_at, User.first_name).where(User.id == user_id))
        ).one()
    assert row.first_name == "Grace" and row.updated_at > row.created_at


async def test_the_schema_step_runs_from_the_environment(engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLYPHH_DATABASE_URL", engine.url.render_as_string(hide_password=False))
    get_settings.cache_clear()
    try:
        await schema.main()
    finally:
        get_settings.cache_clear()
    assert await parent_id(engine)


def test_the_schema_step_runs_as_a_program(engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delitem(sys.modules, "glyphh_server.db.schema")
    monkeypatch.setenv("GLYPHH_DATABASE_URL", engine.url.render_as_string(hide_password=False))
    get_settings.cache_clear()
    try:
        runpy.run_module("glyphh_server.db.schema", run_name="__main__")
    finally:
        get_settings.cache_clear()
