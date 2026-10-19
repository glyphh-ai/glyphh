"""Every tool by name, as tools/list shows it, and calling one: its arguments checked, run in a savepoint so a refusal
leaves nothing half done, a refusal answered as a tool error carrying the API's error."""

from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from glyphh_server.api.errors import error_body
from glyphh_server.errors import GlyphhError, Invalid
from glyphh_server.mcp import panel
from glyphh_server.mcp.protocol import INVALID_PARAMS, RpcError
from glyphh_server.mcp.tools import account, billing, grants, logs, machines, people, runtime, self_hosted
from glyphh_server.mcp.tools.base import Context, Tool

TOOLS: dict[str, Tool] = {
    t.name: t
    for t in (
        *account.TOOLS,
        *billing.TOOLS,
        *people.TOOLS,
        *grants.TOOLS,
        *runtime.TOOLS,
        *machines.TOOLS,
        *self_hosted.TOOLS,
        *logs.TOOLS,
    )
}


def listed(tool: Tool, with_panel: bool) -> dict[str, Any]:
    shown: dict[str, Any] = {
        "name": tool.name,
        "title": tool.title,
        "description": tool.description,
        "inputSchema": tool.args.model_json_schema(),
        "annotations": {"title": tool.title, "readOnlyHint": tool.read_only, "openWorldHint": False},
    }
    if tool.panel and with_panel:
        shown["_meta"] = {"ui": {"resourceUri": panel.URI}}
    return shown


def refused(err: GlyphhError) -> dict[str, Any]:
    body = error_body(err.code, err.message, **err.detail)
    return {"content": [{"type": "text", "text": err.message}], "structuredContent": body, "isError": True}


async def call(ctx: Context, params: dict[str, Any]) -> dict[str, Any]:
    tool = TOOLS.get(params.get("name", ""))
    if tool is None:
        raise RpcError(INVALID_PARAMS, f"There is no tool {params.get('name')!r}.")
    try:
        args = tool.args.model_validate(params.get("arguments") or {})
    except ValidationError as err:
        problems = jsonable_encoder(err.errors(include_url=False))
        return refused(Invalid("The tool's arguments are not valid.", problems=problems))
    try:
        async with ctx.conn.begin_nested():
            done = await tool.handler(ctx, args)
    except GlyphhError as err:
        return refused(err)
    return {"content": [{"type": "text", "text": done.text}], "structuredContent": done.data, "isError": False}
