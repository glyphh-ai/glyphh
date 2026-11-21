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
    ada_beam,
    ada_cases,
    ada_jobs,
    ada_keys,
    ada_models,
    ada_releases,
    apps,
    billing,
    bot_market,
    bot_runs,
    bots,
    connections,
    grants,
    people,
    runtime,
    self_hosted,
    templates,
    tokens,
)
from glyphh_server.mcp.tools.base import Context, Tool
from glyphh_server.ops.templates import installs

_WORKERS = (*ada_models.TOOLS, *ada_cases.TOOLS, *ada_beam.TOOLS, *ada_jobs.TOOLS, *ada_releases.TOOLS)
ADA: dict[str, Tool] = {t.name: t for t in (*_WORKERS, *ada_keys.TOOLS, *templates.TOOLS)}
# Tools that wait on an Ada worker (up to 30 s, a job up to 50): run after the request's transaction has ended, on
# short transactions of their own. A transaction open across the wait holds back the database's oldest snapshot, and an
# import's concurrent index build waits out every such transaction. A tool an installed template adds (glyphh_*, the
# person's own: listed by `listing`) waits on a worker too.
DETACHED: frozenset[str] = frozenset(t.name for t in _WORKERS) | templates.DETACHED
# The bots' tools that call Pipedream or make a run: on transactions of their own too.
DETACHED |= bot_runs.DETACHED | connections.DETACHED
MINE: str = "glyphh_"
_BOTS = (*bots.TOOLS, *bot_runs.TOOLS, *bot_market.TOOLS, *connections.TOOLS)
_OWN = (*account.TOOLS, *billing.TOOLS, *people.TOOLS, *grants.TOOLS, *_BOTS)
TOOLS: dict[str, Tool] = {t.name: t for t in _OWN}
# rrotor's: its runtime keys, self-hosted runtimes and offline licences, and the org's apps: offered only
# while GLYPHH_RROTOR is on, the default.
RROTOR: dict[str, Tool] = {t.name: t for t in (*runtime.TOOLS, *self_hosted.TOOLS, *apps.TOOLS)}
HOSTED: dict[str, Tool] = {t.name: t for t in tokens.TOOLS}  # docs/specs/tokens.md, while GLYPHH_LLM is on


def available(ctx: Context) -> dict[str, Tool]:
    """The tools this server offers: Ada Cloud's too while it is on, rrotor's while it is shown, and topping up the
    hosted models' balance while they are on."""
    tools = TOOLS | RROTOR if ctx.settings.rrotor else TOOLS
    tools = tools | HOSTED if ctx.settings.hosted else tools
    return tools | ADA if ctx.ada is not None else tools


async def listing(ctx: Context) -> dict[str, Tool]:
    """The tools this person sees: what the server offers, and while Ada Cloud is on, their installed templates'."""
    offered = available(ctx)
    if ctx.ada is None:
        return offered
    return offered | templates.mine(await installs.installed(ctx.conn, ctx.who))


def _mine(ctx: Context, name: str) -> bool:
    return ctx.ada is not None and name.startswith(MINE) and name not in available(ctx)


def detached(ctx: Context, method: str, params: dict[str, Any]) -> bool:
    """A call of a tool that waits on a worker (DETACHED, or a template's), while it is offered."""
    name = params.get("name", "")
    return method == "tools/call" and ((name in DETACHED and name in available(ctx)) or _mine(ctx, name))


async def _found(ctx: Context, name: str) -> Tool | None:
    """The tool called: one the server offers, else one of the person's templates' (read on a short transaction of
    its own, the request's having ended)."""
    if _mine(ctx, name):
        return templates.mine(await installs.installed_by(ctx.ada.engine, ctx.who)).get(name)
    return available(ctx).get(name)


def listed(tool: Tool, with_panel: bool) -> dict[str, Any]:
    shown: dict[str, Any] = {
        "name": tool.name,
        "title": tool.title,
        "description": tool.description,
        "inputSchema": tool.args.model_json_schema(),
        "annotations": {"title": tool.title, "readOnlyHint": tool.read_only, "openWorldHint": False},
    }
    if tool.panel and with_panel:
        shown["_meta"] = {"ui": {"resourceUri": tool.resource or panel.URI}}
    return shown


def refused(err: GlyphhError) -> dict[str, Any]:
    body = error_body(err.code, err.message, **err.detail)
    return {"content": [{"type": "text", "text": err.message}], "structuredContent": body, "isError": True}


async def call(ctx: Context, params: dict[str, Any]) -> dict[str, Any]:
    tool = await _found(ctx, params.get("name", ""))
    if tool is None:
        raise RpcError(INVALID_PARAMS, f"There is no tool {params.get('name')!r}.")
    try:
        args = tool.args.model_validate(params.get("arguments") or {})
    except ValidationError as err:
        problems = jsonable_encoder(err.errors(include_url=False))
        return refused(Invalid("The tool's arguments are not valid.", problems=problems))
    try:
        if tool.name in DETACHED or _mine(ctx, tool.name):  # no request transaction: its own short ones
            done = await tool.handler(ctx, args)
        else:
            async with ctx.conn.begin_nested():
                done = await tool.handler(ctx, args)
    except GlyphhError as err:
        return refused(err)
    return {"content": [{"type": "text", "text": done.text}], "structuredContent": done.data, "isError": False}
