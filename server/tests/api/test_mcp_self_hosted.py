"""The connector's self-hosted runtime tools, as Claude uses them: one registered (its environment shown once),
listed with its heartbeat, keyed, and an offline licence issued for it."""

import base64
import json
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_heartbeat import beat, send
from tests.api.test_mcp_tools import _refused
from tests.connector import granted, rpc, tool
from tests.db.helpers import person


async def named(client: Any, auth: dict[str, str], tool_name: str, **arguments: Any) -> dict[str, Any]:
    """A tool whose arguments include a name of their own."""
    return (await rpc(client, auth, "tools/call", name=tool_name, arguments=arguments))["result"]


async def test_a_self_hosted_runtime_is_registered_listed_keyed_and_licensed_from_claude(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Enterprise")
    _, auth = await granted(engine, ada)
    none = await tool(client, auth, "self_runtimes")
    assert none["content"][0]["text"] == "No self-hosted runtimes yet: register_self_runtime adds one."
    made = await named(client, auth, "register_self_runtime", name="Acme", public_url="https://rrotor.acme.test")
    data = made["structuredContent"]
    text = made["content"][0]["text"]
    assert text.startswith("Self-hosted runtime Acme registered at https://rrotor.acme.test.")
    assert f"RROTOR_RUNTIME_TOKEN={data['token']}" in text and "RROTOR_PUBLIC_HOST=rrotor.acme.test" in text
    assert text.endswith("connector at https://rrotor.acme.test/mcp.")
    assert data["mcp_url"] == "https://rrotor.acme.test/mcp"
    _refused(await named(client, auth, "register_self_runtime", name="A", public_url="http://x.test"), "E_INVALID")
    # Listed with where Claude connects to it: a rrotor is its own connector, and Glyphh is never on that path.
    listed = await tool(client, auth, "self_runtimes")
    first, connect = listed["content"][0]["text"].split("\n")
    where = "Claude connects to it at https://rrotor.acme.test/mcp"
    assert first == f"Acme at https://rrotor.acme.test: stopped, id {data['id']}; {where}"
    assert connect == listed["structuredContent"]["connect"] and "secrets_form" in connect and "graph_search" in connect
    kept = listed["structuredContent"]["runtimes"][0]
    assert (kept["mcp_url"], kept["graph"], kept["version"]) == ("https://rrotor.acme.test/mcp", None, None)
    # Its release says whether it keeps the graph: 0.4.0 on does, an older one is said to need an update.
    await send(client, data["token"], beat(version="0.3.0"))
    listed = await tool(client, auth, "self_runtimes")
    old = "stopped, rrotor 0.3.0: before 0.4.0, no graph or secrets form until it is updated, last heartbeat "
    assert listed["content"][0]["text"].startswith(f"Acme at https://rrotor.acme.test: {old}")
    assert listed["structuredContent"]["runtimes"][0]["graph"] is False
    await send(client, data["token"], beat(version="0.4.0"))
    listed = await tool(client, auth, "self_runtimes")
    assert listed["content"][0]["text"].startswith("Acme at https://rrotor.acme.test: stopped, rrotor 0.4.0, last ")
    assert listed["structuredContent"]["runtimes"][0]["graph"] is True
    keyed = await named(client, auth, "create_runtime_key", name="CRM", runtime_id=data["id"])
    assert keyed["structuredContent"]["runtime_id"] == data["id"]
    issued = await tool(client, auth, "offline_licence", runtime_id=data["id"], days=90)
    token = issued["structuredContent"]["token"]
    assert f"\n{token}\n" in issued["content"][0]["text"] and "RROTOR_LICENCE" in issued["content"][0]["text"]
    assert json.loads(base64.urlsafe_b64decode(token))["payload"]["kind"] == "offline"
    _refused(await tool(client, auth, "offline_licence", runtime_id=data["id"], days=400), "E_INVALID")
