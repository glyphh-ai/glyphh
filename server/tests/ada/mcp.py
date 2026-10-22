"""The Glyphh connector beside the Ada API in the same app: /mcp at the account API's host (any host but the Ada
host), called as a 2026-07-28 client, signed in with a connector grant."""

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.connector import UI, granted, modern, modern_headers
from tests.db.helpers import Person

MCP: str = "http://api.test/mcp"


async def signed_in(engine: AsyncEngine, who: Person) -> dict[str, str]:
    return (await granted(engine, who))[1]


async def rpc(http: httpx.AsyncClient, auth: dict[str, str], method: str, **params: Any) -> dict[str, Any]:
    body = modern(method, params, UI)
    res = await http.post(MCP, json=body, headers=modern_headers(body, auth))
    assert res.status_code == 200, res.text
    return dict(res.json())


async def tool(http: httpx.AsyncClient, auth: dict[str, str], called: str, /, **arguments: Any) -> dict[str, Any]:
    """A tool's result, which must not be an error."""
    result = (await rpc(http, auth, "tools/call", name=called, arguments=arguments))["result"]
    assert result["isError"] is False, result
    return dict(result)


async def refused(http: httpx.AsyncClient, auth: dict[str, str], called: str, /, **arguments: Any) -> dict[str, Any]:
    """A tool's refusal: the API's error, its message the text."""
    result = (await rpc(http, auth, "tools/call", name=called, arguments=arguments))["result"]
    assert result["isError"] is True, result
    error = result["structuredContent"]["error"]
    assert result["content"][0]["text"] == error["message"]
    return dict(error)


def text(result: dict[str, Any]) -> str:
    return str(result["content"][0]["text"])


def data(result: dict[str, Any]) -> dict[str, Any]:
    return dict(result["structuredContent"])
