import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.limits import is_limit
from glyphh_server.models import Invite, Membership, Org
from tests.db.helpers import make_org, make_plan, make_user, plan_id


async def _org(engine: AsyncEngine, seats: int | None) -> uuid.UUID:
    plan = f"Seats-{uuid.uuid4().hex[:6]}"
    await make_plan(engine, plan, seats)
    return await make_org(engine, f"Org {plan}", plan)


async def _invite(engine: AsyncEngine, org: uuid.UUID, email: str, **extra: object) -> None:
    async with engine.begin() as conn:
        values = {
            "org_id": org,
            "email": email,
            "role": "user",
            "token_hash": uuid.uuid4().hex,
            "expires_at": datetime.now(UTC) + timedelta(days=7),
            **extra,
        }
        await conn.execute(insert(Invite).values(values))


async def _refused(coro) -> None:
    with pytest.raises(DBAPIError) as caught:
        await coro
    assert is_limit(caught.value)


async def test_members_and_open_invites_together_never_pass_the_seats(engine: AsyncEngine) -> None:
    org = await _org(engine, 2)
    await make_user(engine, org, "one@seats.test")
    await _invite(engine, org, "two@seats.test")
    await _refused(make_user(engine, org, "three@seats.test"))
    await _refused(_invite(engine, org, "four@seats.test"))


async def test_a_disabled_member_a_revoked_or_expired_invite_frees_a_seat(engine: AsyncEngine) -> None:
    org = await _org(engine, 1)
    ada = await make_user(engine, org, "ada@free.test")
    async with engine.begin() as conn:
        await conn.execute(update(Membership).where(Membership.user_id == ada).values(disabled_at=func.now()))
    await _invite(engine, org, "x@free.test", revoked_at=datetime.now(UTC))
    await _invite(engine, org, "y@free.test", expires_at=datetime.now(UTC) - timedelta(seconds=1))
    await _invite(engine, org, "z@free.test", declined_at=datetime.now(UTC))
    bob = await make_user(engine, org, "bob@free.test")

    async def reenable() -> None:
        async with engine.begin() as conn:
            await conn.execute(update(Membership).where(Membership.user_id == ada).values(disabled_at=None))

    await _refused(reenable())
    async with engine.begin() as conn:
        await conn.execute(update(Membership).where(Membership.user_id == bob).values(role="org_admin"))


async def test_no_limit_means_no_limit(engine: AsyncEngine) -> None:
    org = await _org(engine, None)
    for i in range(5):
        await make_user(engine, org, f"m{i}@unlimited.test")


async def test_a_downgrade_cuts_no_one_off_but_adds_nobody(engine: AsyncEngine) -> None:
    org = await _org(engine, 3)
    for i in range(3):
        await make_user(engine, org, f"d{i}@down.test")
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == org).values(plan_id=await plan_id(engine, "Free")))
        kept = (
            await conn.execute(select(func.count()).select_from(Membership).where(Membership.org_id == org))
        ).scalar()
    assert kept == 3
    await _refused(make_user(engine, org, "d9@down.test"))


async def test_ten_at_once_for_two_seats_exactly_two_get_in(engine: AsyncEngine) -> None:
    org = await _org(engine, 2)
    results = await asyncio.gather(
        *(make_user(engine, org, f"r{i}@race.test") for i in range(10)), return_exceptions=True
    )
    assert sum(isinstance(r, uuid.UUID) for r in results) == 2
    assert all(is_limit(r) for r in results if not isinstance(r, uuid.UUID))


def test_is_limit_knows_its_own_mark() -> None:
    assert is_limit(Exception("E_LIMIT seats 1")) and not is_limit(Exception("something else"))
