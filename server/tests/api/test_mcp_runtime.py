"""The connector's runtime key tools: a self-hosted runtime's keys made (shown once), listed and revoked, as Claude
does it; none of the hosted runtime tools is offered."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.connector import granted, rpc, tool
from tests.db.helpers import person
from tests.link import self_runtime


async def key_tool(client: Any, auth: dict[str, str], **arguments: Any) -> dict[str, Any]:
    return (await rpc(client, auth, "tools/call", name="create_runtime_key", arguments=arguments))["result"]


async def test_a_self_hosted_runtimes_keys_are_made_listed_and_revoked_from_claude(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Pro")
    _, auth = await granted(engine, ada)
    runtime = await self_runtime(engine, ada)
    assert (await tool(client, auth, "runtime_keys"))["content"][0]["text"] == "No runtime keys yet."
    made = await key_tool(client, auth, name="Claude", expires_in_days=30, runtime_id=str(runtime.id))
    key = made["structuredContent"]["key"]
    assert (
        key.startswith("glyphh_rk_")
        and f"Runtime key Claude: {key}\nShown once, expires " in made["content"][0]["text"]
    )
    forever = await key_tool(client, auth, name="CRM", runtime_id=str(runtime.id))
    assert "expires never" in forever["content"][0]["text"]
    listed = await tool(client, auth, "runtime_keys")
    assert (
        listed["content"][0]["text"].startswith("Claude, made ") and "key" not in listed["structuredContent"]["keys"][0]
    )
    gone = await tool(client, auth, "revoke_runtime_key", key_id=made["structuredContent"]["id"])
    assert gone["content"][0]["text"] == "Runtime key Claude is revoked."
    assert "revoked" in (await tool(client, auth, "runtime_keys"))["content"][0]["text"]
    tools = {t["name"] for t in (await rpc(client, auth, "tools/list"))["result"]["tools"]}
    hosting = {"runtime", "runtimes", "start_runtime", "stop_runtime", "restart_runtime", "create_runtime", "logs"}
    assert tools & (hosting | {"delete_runtime"}) == set()
