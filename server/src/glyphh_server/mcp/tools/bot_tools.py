"""The tools the org's bots add to its connector by purpose (ops/bots/exposed.py): each bot's declared tools, listed
by their own names (a name the server's own tools or another bot's have already becomes <name>__<slug>), found by
Claude's tool search like any tool, each calling its bot: a run with its arguments as the message (waited on, answered
with what the bot said and what its `verdicts` decision decided), its recent runs each so, a decision's verdict
corrected, a waiting run answered. They make runs, so each is called on transactions of its own (registry.detached),
the request's having ended."""

import asyncio
import json
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, create_model
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.db import tenancy
from glyphh_server.errors import Invalid
from glyphh_server.mcp.tools.base import Context, Done, Tool, dump
from glyphh_server.mcp.tools.bot_runs import run_line
from glyphh_server.models import Bot
from glyphh_server.ops.bots import runs, store
from glyphh_server.ops.bots.exposed import ConnectorTool
from glyphh_server.ops.bots.views import RunView, WrongIn

GOING: tuple[str, ...] = ("queued", "running", "dispatched")
POLL: float = 0.5
NAME_MAX: int = 64
NOT_ITS: str = "That run is not one of this bot's."
SHOWN: int = 20


class NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Wrong(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: uuid.UUID = Field(description="The run whose verdict was wrong")
    outcome: str = Field(min_length=1, max_length=200, description="What the verdict should have been")
    item: str | None = Field(None, max_length=200, description="Which item, for a run over many: its key")


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: uuid.UUID = Field(description="The run that waits on you")
    answer: str | dict[str, str] = Field(description="One of its question's options; a batch: N=option, rest=option")


def _args(tool: ConnectorTool) -> type[BaseModel]:
    """op run's arguments: the text fields it declares; the others' are fixed."""
    if tool.op == "wrong":
        return Wrong
    if tool.op == "answer":
        return Answer
    fields: dict[str, Any] = {
        a: (str, Field(max_length=200_000, description=about))
        if a in tool.required
        else (str | None, Field(None, max_length=200_000, description=about))
        for a, about in tool.args.items()
    }
    return create_model(f"Args_{tool.name}", __config__=ConfigDict(extra="forbid"), **fields)


def verdicts(run: RunView, decision: str | None) -> dict[str, Any]:
    """The run, shortly: what the bot said, what its `decision` decided so far, item by item (each {id, item,
    outcome, by, confidence}), and what it asks, when it waits."""
    shown: dict[str, Any] = {"run_id": str(run.id), "status": run.status, "input": run.input[:300]}
    shown["output"] = run.output
    if decision is not None:
        shown["verdicts"] = (run.data.get(decision) or {}).get("decisions", [])
    if run.question is not None:
        shown["question"] = run.question.model_dump(mode="json")
    return shown | ({"error": run.error} if run.error else {})


async def _waited(ctx: Context, run: RunView, seconds: int) -> RunView:
    """The run once it ends (or waits on the person), or as it is after `seconds`."""
    left = seconds / POLL
    while run.status in GOING and left > 0:
        await asyncio.sleep(POLL)
        left -= 1
        async with ctx.bots.engine.begin() as conn:
            await tenancy.enter(conn, ctx.who.org_id)
            run = await runs.get(conn, run.id)
    return run


async def _its(ctx: Context, slug: str, run_id: uuid.UUID) -> None:
    async with ctx.bots.engine.begin() as conn:
        await tenancy.enter(conn, ctx.who.org_id)
        if (await runs.get(conn, run_id)).bot_slug != slug:
            raise Invalid(NOT_ITS, reason="run", run_id=str(run_id))


async def _run(ctx: Context, slug: str, tool: ConnectorTool, args: BaseModel) -> Done:
    given = args.model_dump(exclude_none=True)
    text = str(given.get(tool.given, "")) if tool.given else json.dumps(given)
    run = await _waited(ctx, await ctx.bots.start(ctx.who, slug, text), tool.wait)
    return Done(run_line(run), verdicts(run, tool.verdicts))


async def _runs(ctx: Context, slug: str, tool: ConnectorTool, _: BaseModel) -> Done:
    async with ctx.bots.engine.begin() as conn:
        await tenancy.enter(conn, ctx.who.org_id)
        found = (await runs.listing(conn, await store.row(conn, slug)))[:SHOWN]
    shown = [verdicts(r, tool.verdicts) for r in found]
    return Done("\n".join(run_line(r) for r in found) or "No runs yet.", {"runs": shown})


async def _wrong(ctx: Context, slug: str, tool: ConnectorTool, args: Wrong) -> Done:
    await _its(ctx, slug, args.run_id)
    said: dict[str, Any] = await ctx.bots.wrong(
        ctx.who, args.run_id, WrongIn(outcome=args.outcome, gate=tool.gate, item=args.item)
    )
    return Done(f"Decision {said['gate']} said {said['said']}; Ada learned {said['now']}.", said)


async def _answer(ctx: Context, slug: str, tool: ConnectorTool, args: Answer) -> Done:
    await _its(ctx, slug, args.run_id)
    run = await ctx.bots.answer(ctx.who, args.run_id, args.answer)
    return Done(f"Run {run.id} carries on.", dump(run))


OPS: dict[str, Any] = {"run": _run, "runs": _runs, "wrong": _wrong, "answer": _answer}


def _tool(name: str, bot: Any, tool: ConnectorTool) -> Tool:
    async def handler(ctx: Context, args: Any) -> Done:
        done: Done = await OPS[tool.op](ctx, bot.slug, tool, args)
        return done

    about = f"{tool.description} (the {bot.name} bot)"
    return Tool(name, tool.title or name, about, _args(tool), handler, tool.op == "runs")


async def offered(conn: AsyncConnection, taken: set[str]) -> dict[str, Tool]:
    """The org's bots' tools by name (conn in the org): a name already taken gets its bot's slug after it."""
    found: dict[str, Tool] = {}
    declared = select(Bot.slug, Bot.name, Bot.connector_tools).order_by(Bot.created_at, Bot.slug)
    for bot in await conn.execute(declared):
        for given in bot.connector_tools:
            tool = ConnectorTool.model_validate(given)
            name = tool.name if tool.name not in taken | found.keys() else f"{tool.name}__{bot.slug}"[:NAME_MAX]
            found[name] = _tool(name, bot, tool)
    return found


async def one(ctx: Context, taken: set[str], name: str) -> Tool | None:
    """The bot's tool called `name`, read on a short transaction of its own."""
    async with ctx.bots.engine.begin() as conn:
        await tenancy.enter(conn, ctx.who.org_id)
        return (await offered(conn, taken)).get(name)
