"""The connector's machine tools: machines listed, made, started, stopped and restarted by id, and deleted with the
name typed to confirm, as Claude does it."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import Rrotor
from tests.api.test_hosted import FLY_SETTINGS
from tests.api.test_mcp_tools import _refused
from tests.conftest import _client
from tests.connector import granted, rpc, tool
from tests.db.helpers import person
from tests.fakes import FakeFly, fake_http


async def test_machines_are_made_driven_and_deleted_from_claude(engine: AsyncEngine) -> None:
    fly = FakeFly()
    ada = await person(engine, "Pro")
    _, auth = await granted(engine, ada)
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=fly))):
        none = await tool(client, auth, "runtimes")
        assert none["content"][0]["text"] == "You have no hosted machines yet: create_runtime makes one."
        args = {"name": "research", "size": "medium"}
        made = (await rpc(client, auth, "tools/call", name="create_runtime", arguments=args))["result"]
        machine = made["structuredContent"]
        assert made["content"][0]["text"] == (
            f"research (medium) is stopped at https://m_2.glyphh.app, 0.0 h this month, id {machine['id']}. Add it to"
            " Claude as a connector: its /mcp, with a runtime key."
        )
        listed = await tool(client, auth, "runtimes")
        assert [m["name"] for m in listed["structuredContent"]["runtimes"]] == ["research"]
        assert listed["content"][0]["text"].startswith("research (medium) is stopped")
        stopped = await tool(client, auth, "stop_runtime", id=machine["id"])
        assert stopped["content"][0]["text"].endswith(f"id {machine['id']}.")
        assert fly.machines["m_2"]["state"] == "stopped"
        started = await tool(client, auth, "start_runtime", id=machine["id"])
        assert "Add it to Claude" in started["content"][0]["text"] and fly.machines["m_2"]["state"] == "started"
        restarted = await tool(client, auth, "restart_runtime", id=machine["id"])
        assert restarted["structuredContent"]["state"] == "stopped" and fly.calls[-1][1] == "/machines/m_2/restart"
        async with engine.begin() as conn:
            now = datetime.now(UTC)
            values = {"month_seconds": 5400, "month": now.strftime("%Y-%m")}
            await conn.execute(update(Rrotor).where(Rrotor.id == uuid.UUID(machine["id"])).values(**values))
        counted = (await tool(client, auth, "runtimes"))["content"][0]["text"]
        assert ", 1.5 h this month, id " in counted
        _refused(await tool(client, auth, "delete_runtime", id=machine["id"], confirm="Research"), "E_INVALID")
        gone = await tool(client, auth, "delete_runtime", id=machine["id"], confirm="research")
        assert gone["content"][0]["text"] == "research is deleted: its machine and its disk are gone."
        assert gone["structuredContent"] == {"id": machine["id"], "deleted": True} and "m_2" not in fly.machines
        _refused(await tool(client, auth, "restart_runtime", id=machine["id"]), "E_NOT_FOUND")
        _refused(await tool(client, auth, "stop_runtime"), "E_NOT_FOUND")
