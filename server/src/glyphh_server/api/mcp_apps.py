"""MCP Apps for the platform, which is their host when a bot's turn shows one inline (a run's `apps`,
ops/bots/shown.py): the page of a UI resource of the server's own (`ui://glyphh/...`, mcp/panel.py: the decision
card, the apps and account panels), and a connector tool called for a page through the host's bridge (the page's
`tools/call`), run as the person signed in to the platform, exactly as the connector runs it (mcp/tools/registry.py).
A page some other server's tool result embeds comes with the run itself; nothing is fetched for it here."""

from typing import Annotated, Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.api.auth import Bearer, Caller, authenticate
from glyphh_server.errors import NotFound
from glyphh_server.mcp import panel
from glyphh_server.mcp.protocol import RpcError
from glyphh_server.mcp.tools import registry
from glyphh_server.mcp.tools.base import Context

router = APIRouter(tags=["mcp apps"])


class CallIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200, description="The connector tool the page calls")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Its arguments")


@router.get("/v1/mcp-apps/resource", operation_id="readMcpAppResource")
async def read_resource(caller: Caller, uri: Annotated[str, Query(max_length=200)]) -> dict[str, Any]:
    """A UI resource of the server's own, as the connector's resources/read answers it: its page and how to frame it."""
    if uri not in panel.PAGES:
        raise NotFound("There is no such MCP App here.", uri=uri)
    return panel.contents(uri)


@router.post("/v1/mcp-apps/tools/call", operation_id="callMcpAppTool")
async def call_tool(body: CallIn, request: Request, creds: Bearer) -> dict[str, Any]:
    """The tool's result as MCP has it (`content`, `structuredContent`, `isError`). One transaction, but for a tool
    that waits on a worker or makes runs, which is called once it has ended (as /mcp does)."""
    state = request.app.state
    params = {"name": body.name, "arguments": body.arguments}
    async with state.engine.begin() as conn:
        who = await authenticate(conn, creds, state.settings.mcp_resource)
        ctx = Context(conn, who, state.settings, state.http, state.hub, state.signing_key, state.ada, state.bots)
        if not registry.detached(ctx, "tools/call", params):
            return await _called(ctx, params)
    return await _called(ctx, params)


async def _called(ctx: Context, params: dict[str, Any]) -> dict[str, Any]:
    try:
        return await registry.call(ctx, params)
    except RpcError as err:
        raise NotFound(err.message, tool=params["name"]) from None
