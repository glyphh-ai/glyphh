import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Conflict, Forbidden, Invalid, LimitReached, NotFound
from glyphh_server.models import Invite, Membership, User
from glyphh_server.ops import invites
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.signin import personal_org
from tests.db.helpers import admin_of, make_plan, make_user


async def test_an_admin_invites_lists_and_withdraws(engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "Invite Co")
    async with engine.begin() as conn:
        view, token = await invites.create_invite(conn, boss, " New@Invite.Test ", "org_admin")
        assert (view.email, view.role) == ("new@invite.test", "org_admin") and len(token) >= 43
        assert [i.id for i in await invites.list_invites(conn, boss)] == [view.id]
        assert (await invites.read_invite(conn, token)).org == "Invite Co"
        await invites.revoke_invite(conn, boss, view.id)
        assert await invites.list_invites(conn, boss) == []
        with pytest.raises(NotFound):
            await invites.revoke_invite(conn, boss, view.id)
        with pytest.raises(Invalid):
            await invites.read_invite(conn, token)


async def test_only_admins_invite_and_never_twice_or_past_the_seats(engine: AsyncEngine) -> None:
    await make_plan(engine, "One Seat Plus", 2)
    boss = await admin_of(engine, "Strict Invite Co", "One Seat Plus")
    await make_user(engine, boss.org_id, "taken@strict.test")
    async with engine.begin() as conn:
        with pytest.raises(Forbidden):
            await invites.create_invite(conn, boss.model_copy(update={"role": "user"}), "x@strict.test", "user")
        with pytest.raises(Conflict, match="already in your org"):
            await invites.create_invite(conn, boss, "TAKEN@strict.test", "user")
        with pytest.raises(LimitReached):
            await invites.create_invite(conn, boss, "full@strict.test", "user")
    big = await admin_of(engine, "Twice Co")
    async with engine.begin() as conn:
        await invites.create_invite(conn, big, "twice@twice.test", "user")
    async with engine.begin() as conn:
        with pytest.raises(Conflict, match="open invite"):
            await invites.create_invite(conn, big, "twice@twice.test", "user")


async def test_nobody_is_invited_into_a_personal_org(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        me = (await conn.execute(insert(User).values(email="solo@personal.test").returning(User.id))).scalar_one()
        org = await personal_org(conn, me)
        with pytest.raises(Forbidden) as caught:
            await invites.create_invite(conn, Principal(user_id=me, org_id=org, role="org_admin"), "x@y.test", "user")
    assert caught.value.detail == {"reason": "personal"}


async def test_accepting_adds_a_membership_for_the_invited_person_only_once(engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "Accept Co")
    elsewhere = await admin_of(engine, "Their Own Co")
    joiner = await make_user(engine, elsewhere.org_id, "Joiner@Accept.test")
    stranger = await make_user(engine, elsewhere.org_id, "someone@else.test")
    async with engine.begin() as conn:
        _, token = await invites.create_invite(conn, boss, "joiner@accept.test", "org_admin")
    async with engine.begin() as conn:
        with pytest.raises(Forbidden, match=r"joiner@accept\.test"):
            await invites.accept_invite(conn, token, stranger)
    async with engine.begin() as conn:
        assert await invites.accept_invite(conn, token, joiner) == "Accept Co"
        orgs = dict(
            (await conn.execute(select(Membership.org_id, Membership.role).where(Membership.user_id == joiner))).all()
        )
    assert orgs == {boss.org_id: "org_admin", elsewhere.org_id: "user"}
    async with engine.begin() as conn:
        with pytest.raises(Invalid):
            await invites.accept_invite(conn, token, joiner)


async def test_the_invited_person_can_decline_and_the_seat_is_free(engine: AsyncEngine) -> None:
    await make_plan(engine, "Two Seats Decline", 2)
    boss = await admin_of(engine, "Decline Co", "Two Seats Decline")
    them = await make_user(engine, (await admin_of(engine, "Theirs Co")).org_id, "no@decline.test")
    async with engine.begin() as conn:
        _, token = await invites.create_invite(conn, boss, "no@decline.test", "user")
        with pytest.raises(Forbidden):
            await invites.decline_invite(conn, token, boss.user_id)
        await invites.decline_invite(conn, token, them)
        with pytest.raises(Invalid):
            await invites.read_invite(conn, token)
        await invites.create_invite(conn, boss, "next@decline.test", "user")


async def test_an_expired_invite_or_one_raced_away_cannot_be_used(engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "Late Invite Co")
    racer = await make_user(engine, (await admin_of(engine, "Racer Co")).org_id, "race@late.test")
    async with engine.begin() as conn:
        view, token = await invites.create_invite(conn, boss, "late@late.test", "user")
        await conn.execute(
            update(Invite).where(Invite.id == view.id).values(expires_at=datetime.now(UTC) - timedelta(1))
        )
        with pytest.raises(Invalid):
            await invites.read_invite(conn, token)
    async with engine.begin() as conn:
        view2, token2 = await invites.create_invite(conn, boss, "race@late.test", "user")
    from unittest.mock import patch

    async def raced(*_: object) -> invites.OpenInvite:
        return invites.OpenInvite(
            org="Late Invite Co", email="race@late.test", role="user", expires_at=datetime.now(UTC)
        )

    async with engine.begin() as conn:
        await conn.execute(update(Invite).where(Invite.id == view2.id).values(accepted_at=datetime.now(UTC)))
        with patch.object(invites, "read_invite", raced), pytest.raises(Invalid):
            await invites.accept_invite(conn, token2, racer)


async def test_someone_who_joined_meanwhile_is_told_they_are_already_in(engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "Meanwhile Co")
    async with engine.begin() as conn:
        _, token = await invites.create_invite(conn, boss, "meanwhile@x.test", "user")
    await make_user(engine, boss.org_id, "meanwhile@x.test")
    async with engine.begin() as conn:
        person = (await conn.execute(select(User.id).where(User.email == "meanwhile@x.test"))).scalar_one()
        with pytest.raises(Conflict, match="already in that org"):
            await invites.accept_invite(conn, token, person)
    assert uuid.UUID(str(boss.org_id))
