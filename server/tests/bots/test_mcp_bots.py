"""The connector's bots and connections tools, called as Claude calls them."""

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.bots.conftest import Served
from tests.bots.fakes import account, reply, text
from tests.connector import granted, rpc, tool
from tests.db.helpers import person

BOT_TOOLS = {
    "bots",
    "bot",
    "bot_create",
    "bot_update",
    "bot_delete",
    "bot_connections_set",
    "bot_models",
    "bot_run",
    "bot_runs",
    "bot_run_get",
    "connections",
    "connection_apps",
    "connection_link",
    "connection_tools",
}


async def test_a_bot_is_made_scoped_and_run_through_the_connector(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    _, auth = await granted(engine, ada)
    listed = {t["name"] for t in (await rpc(served.http, auth, "tools/list"))["result"]["tools"]}
    assert listed >= BOT_TOOLS
    link = await tool(served.http, auth, "connection_link", app="gmail")
    assert link["isError"] is False and link["structuredContent"]["url"].endswith("&app=gmail")
    served.pd.accounts.append(account("apn_9"))
    found = (await tool(served.http, auth, "connections"))["structuredContent"]["connections"]
    assert [c["account_id"] for c in found] == ["apn_9"]
    tools = (await tool(served.http, auth, "connection_tools", connection_id=found[0]["id"]))["structuredContent"]
    assert [t["key"] for t in tools["tools"]] == ["gmail-send-email", "gmail-find-email"]
    given = {"name": "Desk Cat", "look": {"head": "flat"}, "instructions": "Tidy up."}
    made = (await rpc(served.http, auth, "tools/call", name="bot_create", arguments=given))["result"]
    assert made["isError"] is False and made["structuredContent"]["slug"] == "desk-cat"
    scopes = [{"connection_id": found[0]["id"], "tools": ["gmail-find-email"]}]
    scoped = await tool(served.http, auth, "bot_connections_set", slug="desk-cat", connections=scopes)
    assert scoped["structuredContent"]["connections"][0]["tools"] == ["gmail-find-email"]
    served.claude.replies = [reply(text("All tidy."))]
    started = await tool(served.http, auth, "bot_run", slug="desk-cat", input="Go")
    assert started["isError"] is False and started["structuredContent"]["status"] == "queued"
    await served.settled()
    got = await tool(served.http, auth, "bot_run_get", run_id=started["structuredContent"]["id"])
    assert got["structuredContent"]["status"] == "done" and got["structuredContent"]["output"] == "All tidy."
    assert len((await tool(served.http, auth, "bot_runs", slug="desk-cat"))["structuredContent"]["runs"]) == 1
    changed = await tool(served.http, auth, "bot_update", slug="desk-cat", summary="Keeps the desk")
    assert changed["structuredContent"]["summary"] == "Keeps the desk"
    assert "claude-opus-5-5" in (await tool(served.http, auth, "bot_models"))["content"][0]["text"]
    assert (await tool(served.http, auth, "bot_delete", slug="desk-cat"))["isError"] is False
    missing = await tool(served.http, auth, "bot", slug="desk-cat")
    assert missing["isError"] is True and missing["structuredContent"]["error"]["code"] == "E_NOT_FOUND"
