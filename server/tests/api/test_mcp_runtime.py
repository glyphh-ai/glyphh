"""The connector's runtime tools: the runtime shown, started and stopped, and its keys made (shown once), listed and
revoked, as Claude does it."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from tests.api.test_hosted import FLY_SETTINGS
from tests.conftest import _client
from tests.connector import granted, rpc, tool
from tests.db.helpers import person
from tests.fakes import FakeFly, fake_http


async def key_tool(client: Any, auth: dict[str, str], **arguments: Any) -> dict[str, Any]:
    return (await rpc(client, auth, "tools/call", name="create_runtime_key", arguments=arguments))["result"]


async def test_the_runtime_is_started_shown_keyed_and_stopped_from_claude(engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    _, auth = await granted(engine, ada)
    async for client in _client(create_app(FLY_SETTINGS, http=fake_http(fly=FakeFly()))):
        none = await tool(client, auth, "runtime")
        assert none["content"][0]["text"] == "You have no hosted runtime yet: start_runtime makes one."
        started = await tool(client, auth, "start_runtime")
        text = started["content"][0]["text"]
        assert text.startswith("Your runtime is stopped at https://m_2.glyphh.app, 0.0 h this month.")
        assert "Add it to Claude as a connector" in text and started["structuredContent"]["state"] == "stopped"
        assert (await tool(client, auth, "runtime_keys"))["content"][0]["text"] == "No runtime keys yet."
        made = await key_tool(client, auth, name="Claude", expires_in_days=30)
        key = made["structuredContent"]["key"]
        assert (
            key.startswith("glyphh_rk_")
            and f"Runtime key Claude: {key}\nShown once, expires " in made["content"][0]["text"]
        )
        listed = await tool(client, auth, "runtime_keys")
        assert (
            listed["content"][0]["text"].startswith("Claude, made ")
            and "key" not in listed["structuredContent"]["keys"][0]
        )
        gone = await tool(client, auth, "revoke_runtime_key", key_id=made["structuredContent"]["id"])
        assert gone["content"][0]["text"] == "Runtime key Claude is revoked."
        assert "revoked" in (await tool(client, auth, "runtime_keys"))["content"][0]["text"]
        stopped = await tool(client, auth, "stop_runtime")
        assert stopped["structuredContent"]["state"] == "stopped"
        shown = await tool(client, auth, "runtime")
        assert shown["content"][0]["text"] == "Your runtime is stopped at https://m_2.glyphh.app, 0.0 h this month."
