import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import NotFound
from glyphh_server.ops.auth import hosts, tokens
from tests.db.helpers import make_client, make_org, make_user


async def test_a_registered_host_is_found_by_its_client_id(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await hosts.register(conn, "codex-host", "Codex", ["http://127.0.0.1:1455/auth/callback"])
        found = await hosts.find(conn, "codex-host")
        missing = await hosts.find(conn, "nobody")
    assert (
        found is not None and found.name == "Codex" and found.redirect_uris == ["http://127.0.0.1:1455/auth/callback"]
    )
    assert missing is None


async def test_a_member_sees_their_connected_hosts_and_disconnects_one(engine: AsyncEngine) -> None:
    user = await make_user(engine, await make_org(engine, "Hosts Co"), "hosts@ops.test")
    claude, codex = await make_client(engine, "list-claude"), await make_client(engine, "list-codex")
    async with engine.begin() as conn:
        await tokens.issue(conn, user, claude)
        await tokens.issue(conn, user, claude)
        await tokens.issue(conn, user, codex)
        await tokens.issue(conn, user)
        assert {h.id for h in await hosts.connected(conn, user)} == {claude, codex}
        await hosts.disconnect(conn, user, claude)
        assert [h.id for h in await hosts.connected(conn, user)] == [codex]
        with pytest.raises(NotFound) as caught:
            await hosts.disconnect(conn, user, claude)
        assert caught.value.detail == {"host_id": str(claude)}
        with pytest.raises(NotFound):
            await hosts.disconnect(conn, user, uuid.uuid4())
