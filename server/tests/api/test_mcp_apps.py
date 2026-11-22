"""MCP Apps for the platform: the page of a UI resource of the server's own, and a connector tool called for a page
as the person signed in."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.mcp import panel
from tests.db.helpers import person


async def test_the_page_of_a_ui_resource_of_the_servers_own(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    res = await client.get("/v1/mcp-apps/resource", params={"uri": panel.DECISION_URI}, headers=ada.headers)
    assert res.status_code == 200, res.text
    got = res.json()
    assert (got["uri"], got["mimeType"]) == (panel.DECISION_URI, panel.MIME)
    assert got["text"].lstrip().lower().startswith("<!doctype html") and got["_meta"]["ui"]["prefersBorder"] is True
    missing = await client.get("/v1/mcp-apps/resource", params={"uri": "ui://other/card/1"}, headers=ada.headers)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "E_NOT_FOUND"
    assert (await client.get("/v1/mcp-apps/resource", params={"uri": panel.URI})).status_code == 401


async def test_a_page_calls_a_connector_tool_as_the_person(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    res = await client.post("/v1/mcp-apps/tools/call", json={"name": "whoami"}, headers=ada.headers)
    assert res.status_code == 200, res.text
    got = res.json()
    assert got["isError"] is False and got["structuredContent"]["email"] == ada.email
    unknown = await client.post("/v1/mcp-apps/tools/call", json={"name": "no_such_tool"}, headers=ada.headers)
    assert unknown.status_code == 404 and "no_such_tool" in unknown.json()["error"]["message"]
    assert (await client.post("/v1/mcp-apps/tools/call", json={"name": "whoami"})).status_code == 401
