"""Every tool by name, as tools/list shows it, and calling one: its arguments checked, run in a savepoint so a refusal
leaves nothing half done, a refusal answered as a tool error carrying the API's error. Ada Cloud's tools (ada_*, the
API keys) are there only while it is on (GLYPHH_ADA_CLOUD): off, they are neither listed nor called."""

from typing import Any

from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError

from glyphh_server.api.errors import error_body
from glyphh_server.errors import GlyphhError, Invalid
from glyphh_server.mcp import panel
from glyphh_server.mcp.protocol import INVALID_PARAMS, RpcError
from glyphh_server.mcp.tools import (
    account,
    ada_cases,
    ada_jobs,
    ada_keys,
    ada_models,
    billing,
    grants,
    logs,
    machines,
    people,
    runtime,
    self_hosted,
)
from glyphh_server.mcp.tools.base import Context, Tool

ADA: dict[str, Tool] = {t.name: t for t in (*ada_models.TOOLS, *ada_cases.TOOLS, *ada_jobs.TOOLS, *ada_keys.TOOLS)}
# Tools that wait on an Ada worker (up to 30 s, a job up to 50): run after the request's transaction has ended, on
# short transactions of their own. A transaction open across the wait holds back the database's oldest snapshot, and an
# import's concurrent index build waits out every such transaction.
DETACHED: frozenset[str] = frozenset(t.name for t in (*ada_models.TOOLS, *ada_cases.TOOLS, *ada_jobs.TOOLS))
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


def available(ctx: Context) -> dict[str, Tool]:
    """The tools this server offers: Ada Cloud's too while it is on."""
    return TOOLS | ADA if ctx.ada is not None else TOOLS


def detached(ctx: Context, method: str, params: dict[str, Any]) -> bool:
    """A call of a tool that waits on a worker (DETACHED), while it is offered."""
    name = params.get("name", "")
    return method == "tools/call" and name in DETACHED and name in available(ctx)


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
    tool = available(ctx).get(params.get("name", ""))
    if tool is None:
        raise RpcError(INVALID_PARAMS, f"There is no tool {params.get('name')!r}.")
    try:
        args = tool.args.model_validate(params.get("arguments") or {})
    except ValidationError as err:
        problems = jsonable_encoder(err.errors(include_url=False))
        return refused(Invalid("The tool's arguments are not valid.", problems=problems))
    try:
        if tool.name in DETACHED:  # no request transaction: its own short ones
            done = await tool.handler(ctx, args)
        else:
            async with ctx.conn.begin_nested():
                done = await tool.handler(ctx, args)
    except GlyphhError as err:
        return refused(err)
    return {"content": [{"type": "text", "text": done.text}], "structuredContent": done.data, "isError": False}
