import json

import httpx

MCP_HEADERS: dict[str, str] = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


def _sse_result(body: str) -> dict:
    data = [line[len("data:") :].strip() for line in body.splitlines() if line.startswith("data:")]
    return json.loads(data[-1])


async def _call_tool(client: httpx.AsyncClient, name: str) -> dict:
    res = await client.post(
        "/mcp",
        headers=MCP_HEADERS,
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": {}}},
    )
    assert res.status_code == 200, res.text
    return _sse_result(res.text)["result"]


async def test_the_api_reports_ok_with_the_database_up(client: httpx.AsyncClient) -> None:
    res = await client.get("/v1/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "version": "test", "database": True}


async def test_the_api_reports_degraded_without_the_database(client_without_database: httpx.AsyncClient) -> None:
    res = await client_without_database.get("/v1/health")
    assert res.json() == {"status": "degraded", "version": "test", "database": False}


async def test_mcp_lists_the_health_tool(client: httpx.AsyncClient) -> None:
    res = await client.post("/mcp", headers=MCP_HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert res.status_code == 200, res.text
    tools = {t["name"] for t in _sse_result(res.text)["result"]["tools"]}
    assert tools == {"health"}


async def test_mcp_and_the_api_answer_the_same(client: httpx.AsyncClient) -> None:
    api = (await client.get("/v1/health")).json()
    result = await _call_tool(client, "health")
    assert result["structuredContent"] == api
    assert not result.get("isError")


async def test_the_openapi_spec_names_the_operation(client: httpx.AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()
    assert spec["paths"]["/v1/health"]["get"]["operationId"] == "health"
