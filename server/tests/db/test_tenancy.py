"""Row-level security keyed on the org: a request made with a token sees only its own org's rows."""

import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import Identity, Install, Invite, Org, Token, User, Workspace
from tests.db.helpers import member, person


async def test_a_tenant_sees_only_its_own_org(engine: AsyncEngine, client: httpx.AsyncClient) -> None:
    ada = await person(engine, "Team", seats=3)
    bob = await member(engine, ada.org_id)
    eve = await person(engine, "Team", seats=3)
    for who in (ada, eve):
        await client.post("/v1/workspaces", json={"name": "W"}, headers=who.headers)
        await client.post("/v1/org/invites", json={"email": "x@tenancy.test"}, headers=who.headers)
    async with engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        assert set((await conn.execute(select(Org.id))).scalars()) == {ada.org_id}
        assert set((await conn.execute(select(User.id))).scalars()) == {ada.user_id, bob.user_id}
        assert set((await conn.execute(select(Invite.org_id))).scalars()) == {ada.org_id}
        assert set((await conn.execute(select(Install.user_id))).scalars()) == {ada.user_id, bob.user_id}
        assert set((await conn.execute(select(Workspace.user_id))).scalars()) == {ada.user_id}
        assert (await conn.execute(select(func.count()).select_from(Token))).scalar_one() == 2
        assert (await conn.execute(select(func.count()).select_from(Identity))).scalar_one() == 0
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
