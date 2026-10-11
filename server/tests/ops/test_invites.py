import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Conflict, Forbidden, Invalid, LimitReached, NotFound
from glyphh_server.models import Invite, User
from glyphh_server.ops import invites
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
        with pytest.raises(Conflict, match="already has a Glyphh account"):
            await invites.create_invite(conn, boss, "TAKEN@strict.test", "user")
        with pytest.raises(LimitReached):
            await invites.create_invite(conn, boss, "full@strict.test", "user")
    big = await admin_of(engine, "Twice Co")
    async with engine.begin() as conn:
        await invites.create_invite(conn, big, "twice@twice.test", "user")
    async with engine.begin() as conn:
        with pytest.raises(Conflict, match="open invite"):
            await invites.create_invite(conn, big, "twice@twice.test", "user")


async def test_accepting_makes_a_member_as_the_invited_email_only_once(engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "Accept Co")
    async with engine.begin() as conn:
        _, token = await invites.create_invite(conn, boss, "joiner@accept.test", "org_admin")
    async with engine.begin() as conn:
        with pytest.raises(Forbidden, match=r"joiner@accept\.test"):
            await invites.accept_invite(conn, token, "someone@else.test", None, None)
    async with engine.begin() as conn:
        assert await invites.accept_invite(conn, token, "Joiner@Accept.test", "Jo", "In") == "Accept Co"
        row = (
            await conn.execute(
                select(User.org_id, User.role, User.first_name).where(User.email == "joiner@accept.test")
            )
        ).one()
    assert (row.org_id, row.role, row.first_name) == (boss.org_id, "org_admin", "Jo")
    async with engine.begin() as conn:
        with pytest.raises(Invalid):
            await invites.accept_invite(conn, token, "joiner@accept.test", None, None)


async def test_an_expired_invite_or_one_raced_away_cannot_be_used(engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "Late Invite Co")
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
        return invites.OpenInvite(org="Late Invite Co", email="race@late.test", role="user")

    async with engine.begin() as conn:
        await conn.execute(update(Invite).where(Invite.id == view2.id).values(accepted_at=datetime.now(UTC)))
        with patch.object(invites, "read_invite", raced), pytest.raises(Invalid):
            await invites.accept_invite(conn, token2, "race@late.test", None, None)


async def test_an_invite_for_an_email_that_signed_up_meanwhile_is_a_conflict(engine: AsyncEngine) -> None:
    boss = await admin_of(engine, "Meanwhile Co")
    async with engine.begin() as conn:
        _, token = await invites.create_invite(conn, boss, "meanwhile@x.test", "user")
    other = await admin_of(engine, "Elsewhere Co")
    await make_user(engine, other.org_id, "meanwhile@x.test")
    async with engine.begin() as conn:
        with pytest.raises(Conflict):
            await invites.accept_invite(conn, token, "meanwhile@x.test", None, None)
    assert uuid.UUID(str(boss.org_id))
