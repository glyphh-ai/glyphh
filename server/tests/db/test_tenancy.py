"""Row-level security keyed on the org: a request made with a token sees only its own org's rows."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import AdaMeterEvent, Identity, Invite, LlmBalance, LlmLedger, Org, User
from tests.db.helpers import member, person

LATER: datetime = datetime.now(UTC) + timedelta(days=1)


async def test_a_tenant_sees_only_its_own_org(engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    bob = await member(engine, ada.org_id)
    eve = await person(engine, "Team")
    async with engine.begin() as conn:
        for who in (ada, eve):
            invite = {"org_id": who.org_id, "email": "x@tenancy.test", "token_hash": f"t-{who.org_id}"}
            await conn.execute(insert(Invite).values(**invite, expires_at=LATER))
            await conn.execute(insert(LlmBalance).values(org_id=who.org_id, micros=1))
            await conn.execute(insert(LlmLedger).values(org_id=who.org_id, kind="grant", amount_micros=1))
            event = {"org_id": who.org_id, "customer": "cus_x", "period": "2026-11", "requests": 1, "at": LATER}
            await conn.execute(insert(AdaMeterEvent).values(**event))
            await conn.execute(
                insert(Identity).values(user_id=who.user_id, provider="google", provider_user_id=who.email)
            )
    async with engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        assert set((await conn.execute(select(Org.id))).scalars()) == {ada.org_id}
        assert set((await conn.execute(select(User.id))).scalars()) == {ada.user_id, bob.user_id}
        for table in (Invite, LlmBalance, LlmLedger, AdaMeterEvent):
            assert set((await conn.execute(select(table.org_id))).scalars()) == {ada.org_id}, table
        assert set((await conn.execute(select(Identity.user_id))).scalars()) == {ada.user_id}
        gone = await conn.execute(update(User).where(User.id == eve.user_id).values(name="hacked"))
        assert gone.rowcount == 0
        await tenancy.leave(conn)
        assert (await conn.execute(select(func.count()).select_from(Org))).scalar_one() > 1


async def test_a_tenant_cannot_write_a_row_into_another_org(engine: AsyncEngine) -> None:
    ada, eve = await person(engine), await person(engine)
    with pytest.raises(DBAPIError, match="row-level security"):
        async with engine.begin() as conn:
            await tenancy.enter(conn, ada.org_id)
            await conn.execute(update(User).where(User.id == ada.user_id).values(org_id=eve.org_id))
