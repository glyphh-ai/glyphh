import uuid

import pytest
from sqlalchemy import insert
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Conflict, Forbidden, LimitReached, NotFound
from glyphh_server.models import User
from glyphh_server.ops import members, org
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.guards import refusals
from tests.db.helpers import admin_of, make_plan, make_user


async def test_the_org_shows_its_plan_and_seats_and_admins_rename_it(engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "Rename Co")
    await make_user(engine, boss.org_id, "m@rename.test")
    async with engine.begin() as conn:
        view = await org.get_org(conn, boss)
        assert (view.name, view.plan, view.seats_taken, view.max_seats) == ("Rename Co", "Enterprise", 2, None)
        assert (await org.rename_org(conn, boss, "  Renamed Co ")).name == "Renamed Co"
        with pytest.raises(Forbidden):
            await org.rename_org(conn, boss.model_copy(update={"role": "user"}), "Nope")


async def test_admins_change_roles_and_disable_but_never_their_own(engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "Roles Co")
    ada = await make_user(engine, boss.org_id, "ada@roles.test")
    async with engine.begin() as conn:
        assert (await members.update_member(conn, boss, ada, role="org_admin")).role == "org_admin"
        assert (await members.update_member(conn, boss, ada, disabled=True)).disabled is True
        assert (await members.update_member(conn, boss, ada, disabled=False)).disabled is False
        assert (await members.update_member(conn, boss, ada)).email == "ada@roles.test"
        assert len(await members.list_members(conn, boss)) == 2
        with pytest.raises(Forbidden, match="your own"):
            await members.update_member(conn, boss, boss.user_id, role="user")
        with pytest.raises(NotFound):
            await members.update_member(conn, boss, uuid.uuid4(), role="user")


async def test_an_org_always_keeps_one_active_admin(engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "Last Admin Co")
    other = await admin_of(engine, "Other Co")
    helper = Principal(
        user_id=await make_user(engine, boss.org_id, "h@last.test", "org_admin"), org_id=boss.org_id, role="org_admin"
    )
    async with engine.begin() as conn:
        await members.update_member(conn, helper, boss.user_id, role="user")
        for change in ({"role": "user"}, {"disabled": True}):
            with pytest.raises(Conflict, match="at least one active org admin"):
                await members.update_member(
                    conn, boss.model_copy(update={"role": "org_admin"}), helper.user_id, **change
                )
        with pytest.raises(Conflict):
            await members.remove_member(conn, boss.model_copy(update={"role": "org_admin"}), helper.user_id)
        with pytest.raises(NotFound):
            await members.remove_member(conn, other, helper.user_id)


async def test_admins_remove_members_and_super_admins_are_out_of_reach(engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "Remove Co")
    bob = await make_user(engine, boss.org_id, "bob@remove.test")
    root = await make_user(engine, boss.org_id, "root@remove.test", "super_admin")
    async with engine.begin() as conn:
        await members.remove_member(conn, boss, bob)
        assert [m.email for m in await members.list_members(conn, boss)].count("bob@remove.test") == 0
        with pytest.raises(Forbidden, match="Super admins"):
            await members.remove_member(conn, boss, root)
        with pytest.raises(Forbidden, match="org admin"):
            await members.remove_member(conn, boss.model_copy(update={"role": "user"}), root)


async def test_re_enabling_past_the_seats_is_refused_with_e_limit(engine: AsyncEngine) -> None:
    await make_plan(engine, "Two Seats", 2)
    boss = await admin_of(engine, "Full Co", "Two Seats")
    ada = await make_user(engine, boss.org_id, "ada@full.test")
    async with engine.begin() as conn:
        await members.update_member(conn, boss, ada, disabled=True)
    await make_user(engine, boss.org_id, "bob@full.test")
    async with engine.begin() as conn:
        with pytest.raises(LimitReached) as caught:
            await members.update_member(conn, boss, ada, disabled=False)
    assert caught.value.code == "E_LIMIT" and caught.value.detail == {"limit": "seats"}


def test_refusals_translate_clashes_and_pass_other_errors_on() -> None:
    with pytest.raises(Conflict, match="taken"), refusals("taken"):
        raise IntegrityError("x", {}, Exception("unique"))
    with pytest.raises(DBAPIError), refusals("taken"):
        raise DBAPIError("x", {}, Exception("deadlock"))


async def test_a_duplicate_email_is_a_conflict(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        with pytest.raises(Conflict), refusals("taken"):
            await conn.execute(insert(User).values(email="dup@dup.test"))
            await conn.execute(insert(User).values(email="DUP@dup.test"))


async def test_removing_someone_takes_them_out_of_this_org_only(engine: AsyncEngine) -> None:
    from sqlalchemy import select

    from glyphh_server.models import Membership

    boss = await admin_of(engine, "Remove Co")
    other = await admin_of(engine, "Kept Co")
    ann = await make_user(engine, boss.org_id, "ann@remove.test")
    async with engine.begin() as conn:
        await conn.execute(insert(Membership).values(user_id=ann, org_id=other.org_id, role="user"))
        await members.remove_member(conn, boss, ann)
        left = (await conn.execute(select(Membership.org_id).where(Membership.user_id == ann))).scalars().all()
    assert left == [other.org_id]
