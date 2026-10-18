"""/mcp as a protocol: POST only and stateless; MCP 2026-07-28 with its headers checked against the body, and the
earlier initialize revisions; the Origin checked; tools, the account panel and its resource."""

import base64
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.mcp import panel
from glyphh_server.mcp.protocol import Call
from glyphh_server.models import ConnectorToken
from glyphh_server.ops.auth.secrets import hash_secret
from glyphh_server.ops.connector import grants
from tests.connector import MODERN, UI, granted, modern, modern_headers, rpc
from tests.db.helpers import person

PANEL: str = "ui://glyphh/account/3"


async def _auth(engine: AsyncEngine) -> dict[str, str]:
    return (await granted(engine, await person(engine)))[1]


async def _legacy(client: httpx.AsyncClient, auth: dict[str, str], body: object, **headers: str) -> httpx.Response:
    return await client.post("/mcp", json=body, headers={**auth, **headers})


async def test_an_earlier_client_initializes_and_gets_its_version_or_the_newest_earlier_one(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    auth = await _auth(engine)
    body = {"jsonrpc": "2.0", "id": "i", "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}
    res = (await _legacy(client, auth, body)).json()
    assert res["id"] == "i" and res["result"]["protocolVersion"] == "2025-06-18"
    assert res["result"]["capabilities"] == {"tools": {}, "resources": {}}
    assert res["result"]["serverInfo"] == {"name": "glyphh", "title": "Glyphh", "version": "test"}
    assert "resultType" not in res["result"] and res["result"]["instructions"]
    body["params"] = {"protocolVersion": "2099-01-01"}
    assert (await _legacy(client, auth, body)).json()["result"]["protocolVersion"] == "2025-11-25"
    note = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    done = await _legacy(client, auth, note, **{"mcp-protocol-version": "2025-06-18"})
    assert done.status_code == 202 and done.content == b""
    listed = await _legacy(client, auth, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert all(
        t["_meta"]["ui"]["resourceUri"] == PANEL
        for t in listed.json()["result"]["tools"]
        if t["name"] in ("whoami", "plan")
    )


async def test_requests_that_arent_one_json_rpc_message_are_refused(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    auth = await _auth(engine)
    bad = await client.post("/mcp", content=b"{nope", headers=auth)
    assert (bad.status_code, bad.json()["error"]["code"]) == (400, -32700) and "id" not in bad.json()
    for body in (
        [{"jsonrpc": "2.0", "id": 1, "method": "ping"}],
        {"id": 1, "method": "ping"},
        {"jsonrpc": "2.0", "id": None, "method": "ping"},
        {"jsonrpc": "2.0", "id": True, "method": "ping"},
        {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": []},
    ):
        res = await _legacy(client, auth, body)
        assert (res.status_code, res.json()["error"]["code"]) == (400, -32600), body


async def test_an_unknown_method_is_not_found_and_an_unsupported_version_names_the_supported(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    auth = await _auth(engine)
    gone = await _legacy(client, auth, {"jsonrpc": "2.0", "id": 7, "method": "prompts/list"})
    assert (gone.status_code, gone.json()["id"], gone.json()["error"]["code"]) == (200, 7, -32601)
    old = await _legacy(
        client, auth, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, **{"mcp-protocol-version": "2024-11-05"}
    )
    assert old.status_code == 400
    assert old.json()["error"]["data"] == {
        "supported": [MODERN, "2025-11-25", "2025-06-18", "2025-03-26"],
        "requested": "2024-11-05",
    }
    body = modern("prompts/list")
    res = await client.post("/mcp", json=body, headers=modern_headers(body, auth))
    assert (res.status_code, res.json()["error"]["code"]) == (404, -32601)
    body = modern("initialize")
    assert (await client.post("/mcp", json=body, headers=modern_headers(body, auth))).status_code == 404


async def test_a_2026_request_needs_its_meta_and_headers_that_match_the_body(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    auth = await _auth(engine)
    body = modern("tools/call", {"name": "whoami", "arguments": {}})
    good = modern_headers(body, auth)
    cases = [
        (good | {"mcp-protocol-version": "2025-06-18"}, -32020),
        (good | {"mcp-method": "tools/list"}, -32020),
        ({k: v for k, v in good.items() if k != "mcp-method"}, -32020),
        (good | {"mcp-name": "plan"}, -32020),
        (good | {"mcp-name": "=?base64?!!?="}, -32020),
    ]
    for headers, code in cases:
        res = await client.post("/mcp", json=body, headers=headers)
        assert (res.status_code, res.json()["error"]["code"], res.json()["id"]) == (400, code, 1), headers
    encoded = good | {"mcp-name": f"=?base64?{base64.b64encode(b'whoami').decode()}?="}
    assert (await client.post("/mcp", json=body, headers=encoded)).json()["result"]["isError"] is False
    bare = {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}
    res = await client.post("/mcp", json=bare, headers=auth | {"mcp-protocol-version": MODERN, "mcp-method": "ping"})
    assert (res.status_code, res.json()["error"]["code"]) == (400, -32602)
    future = modern("ping")
    future["params"]["_meta"]["io.modelcontextprotocol/protocolVersion"] = "2027-01-01"
    res = await client.post("/mcp", json=future, headers=modern_headers(future, auth))
    assert (res.status_code, res.json()["error"]["code"]) == (400, -32022)


async def test_discover_ping_and_every_2026_result_says_complete_and_who_answered(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    auth = await _auth(engine)
    found = (await rpc(client, auth, "server/discover"))["result"]
    assert found["supportedVersions"] == [MODERN, "2025-11-25", "2025-06-18", "2025-03-26"]
    assert found["capabilities"] == {"tools": {}, "resources": {}} and found["resultType"] == "complete"
    assert found["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "glyphh"
    assert (await rpc(client, auth, "ping"))["result"]["resultType"] == "complete"


async def test_tools_name_the_panel_only_for_a_2026_client_that_shows_panels(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    auth = await _auth(engine)
    tools = {t["name"]: t for t in (await rpc(client, auth, "tools/list"))["result"]["tools"]}
    assert set(tools) == {
        "whoami",
        "plan",
        "usage",
        "plans",
        "upgrade",
        "billing_portal",
        "installs",
        "sign_out_install",
        "members",
        "invite",
        "connector_grants",
        "revoke_grant",
        "runtime",
        "start_runtime",
        "stop_runtime",
        "runtime_keys",
        "create_runtime_key",
        "revoke_runtime_key",
        "runtimes",
        "create_runtime",
        "restart_runtime",
        "delete_runtime",
        "self_runtimes",
        "register_self_runtime",
        "offline_licence",
    }
    assert {n for n, t in tools.items() if "_meta" in t} == {"whoami", "plan", "usage"}
    assert tools["plan"]["_meta"] == {"ui": {"resourceUri": PANEL}}
    assert tools["upgrade"]["inputSchema"]["required"] == ["plan"] and tools["whoami"]["annotations"]["readOnlyHint"]
    assert tools["plans"]["annotations"]["readOnlyHint"] and not tools["upgrade"]["annotations"]["readOnlyHint"]
    for caps in ({}, {"extensions": []}, {"extensions": {"io.modelcontextprotocol/ui": {"mimeTypes": ["text/html"]}}}):
        body = modern("tools/list", caps=caps)
        listed = (await client.post("/mcp", json=body, headers=modern_headers(body, auth))).json()["result"]["tools"]
        assert all("_meta" not in t for t in listed), caps


async def test_the_panel_is_listed_and_read_as_an_mcp_app(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    auth = await _auth(engine)
    assert (await rpc(client, auth, "resources/list"))["result"]["resources"] == [panel.RESOURCE]
    assert (await rpc(client, auth, "resources/templates/list"))["result"]["resourceTemplates"] == []
    (read,) = (await rpc(client, auth, "resources/read", uri=PANEL))["result"]["contents"]
    assert (read["uri"], read["mimeType"], read["_meta"]) == (
        PANEL,
        "text/html;profile=mcp-app",
        {"ui": {"prefersBorder": True}},
    )
    assert read["text"].startswith("<!doctype html>") and "window.McpApp=" in read["text"]
    assert "__APP_JS__" not in read["text"] and "callServerTool" in read["text"]
    gone = await rpc(client, auth, "resources/read", uri="ui://glyphh/other")
    assert gone["error"]["code"] == -32602


async def test_a_token_for_another_resource_expired_or_revoked_is_refused(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    _, elsewhere = await granted(engine, ada, "https://other.test/mcp")
    assert (await client.post("/mcp", json={}, headers=elsewhere)).status_code == 401
    grant_id, auth = await granted(engine, ada)
    assert (await rpc(client, auth, "ping"))["result"]["resultType"] == "complete"
    held = ConnectorToken.token_hash == hash_secret(auth["authorization"].removeprefix("Bearer "))
    async with engine.begin() as conn:
        await conn.execute(update(ConnectorToken).where(held).values(expires_at=datetime.now(UTC)))
    assert (await client.post("/mcp", json={}, headers=auth)).status_code == 401
    grant_id, auth = await granted(engine, ada)
    async with engine.begin() as conn:
        await grants.end(conn, grant_id)
    assert (await client.post("/mcp", json={}, headers=auth)).status_code == 401


async def test_only_post_and_only_allowed_origins(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    auth = await _auth(engine)
    for method in ("GET", "DELETE"):
        res = await client.request(method, "/mcp", headers=auth)
        assert (res.status_code, res.headers["allow"]) == (405, "POST")
    ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    evil = await client.post("/mcp", json=ping, headers=auth | {"origin": "https://evil.test"})
    assert evil.status_code == 403 and evil.json()["error"]["code"] == -32600
    for origin in ("https://claude.ai", "http://localhost:8080", "https://claude.com/"):
        assert (await client.post("/mcp", json=ping, headers=auth | {"origin": origin})).status_code == 200, origin


@pytest.mark.parametrize(("caps", "shown"), [(None, True), ({}, False), (UI, True)])
def test_the_panel_is_shown_by_capability(caps: dict | None, shown: bool) -> None:
    assert panel.shown(Call(1, "tools/list", {}, MODERN if caps is not None else "2025-06-18", caps)) is shown
