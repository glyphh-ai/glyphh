"""A Glyphh bot's runs (docs/specs/bots.md): running one, reading its runs, answering a run that waits on the person,
correcting a gate's call, cancelling a waiting run, and what its gates learned. The tools that go through the runner
make their own transactions (registry.DETACHED)."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.mcp.tools.bots import SLUG, Slug
from glyphh_server.ops.bots import runs, store
from glyphh_server.ops.bots.views import RunView, WrongIn


class RunArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = SLUG
    input: str = Field("", max_length=200_000, description="What the bot is given to work on: $input to its steps")


class RunId(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: uuid.UUID


class Answer(RunId):
    answer: str | dict[str, str] = Field(
        description="One of the question's options; for a batch, N=option for each (rest=option), or a map"
    )


class Wrong(WrongIn):
    run_id: uuid.UUID


def run_line(run: RunView) -> str:
    cost = "on the org's own key" if run.own_key else f"${run.cost_micros / 1_000_000:,.4f} charged"
    if run.question is not None:
        said = f"It asks: {run.question.question} ({', '.join(run.question.options)})"
        if run.question.answer_with:
            said += f"; answer like {run.question.answer_with}"
    else:
        said = run.error or run.output[:300]
    tokens = run.input_tokens + run.output_tokens
    return f"Run {run.id} of {run.bot_slug}: {run.status}, {tokens} tokens, {cost}. {said}".strip()


async def run(ctx: Context, args: RunArgs) -> Done:
    made = await ctx.bots.start(ctx.who, args.slug, args.input)
    return Done(f"Run {made.id} queued: bot_run_get follows it.", dump(made))


async def list_runs(ctx: Context, args: Slug) -> Done:
    found = await runs.listing(ctx.conn, await store.row(ctx.conn, args.slug))
    return Done("\n".join(run_line(r) for r in found) or "No runs yet.", {"runs": [dump(r) for r in found]})


async def approvals(ctx: Context, _: NoArgs) -> Done:
    found = await runs.waiting(ctx.conn)
    return Done(
        "\n".join(run_line(r) for r in found) or "No bot is waiting on you.", {"runs": [dump(r) for r in found]}
    )


async def get_run(ctx: Context, args: RunId) -> Done:
    found = await runs.get(ctx.conn, args.run_id)
    return Done(run_line(found), dump(found))


async def answer(ctx: Context, args: Answer) -> Done:
    found = await ctx.bots.answer(ctx.who, args.run_id, args.answer)
    return Done(f"Run {found.id} carries on: bot_run_get follows it.", dump(found))


async def wrong(ctx: Context, args: Wrong) -> Done:
    said: dict[str, Any] = await ctx.bots.wrong(ctx.who, args.run_id, WrongIn(**args.model_dump(exclude={"run_id"})))
    return Done(f"Gate {said['gate']} said {said['said']}; it learned {said['now']}.", said)


async def cancel(ctx: Context, args: RunId) -> Done:
    found = await ctx.bots.cancel(ctx.who, args.run_id)
    return Done(f"Run {found.id} cancelled.", dump(found))


async def gates(ctx: Context, args: Slug) -> Done:
    found: dict[str, Any] = await ctx.bots.gates(ctx.who, args.slug)
    lines = [f"{name}: {g.get('precedents', 0)} precedents" for name, g in found.items()]
    return Done("\n".join(lines) or "The bot has no gates.", {"gates": found})


def _tool(name: str, title: str, about: str, args: type[BaseModel], handler: object, read_only: bool) -> Tool:
    return Tool(name, title, about, args, handler, read_only)  # type: ignore[arg-type]


TOOLS: tuple[Tool, ...] = (
    _tool(
        "bot_run",
        "Run a bot",
        "Run a bot on an input, in the background. A run that asks waits until bot_run_answer answers it.",
        RunArgs,
        run,
        False,
    ),
    _tool(
        "bot_approvals",
        "Bots waiting on you",
        "The org's approvals queue: every bot run waiting on the person (a gate unsure, an approval, a tool its "
        "connection asks about), each with what it asks. bot_run_answer answers one.",
        NoArgs,
        approvals,
        True,
    ),
    _tool("bot_runs", "A bot's runs", "A bot's runs, the newest first.", Slug, list_runs, True),
    _tool("bot_run_get", "A bot run", "One run: its status, log, data, question, tokens.", RunId, get_run, True),
    _tool(
        "bot_run_answer",
        "Answer a bot",
        "Answer the run that waits on the person (its question says the options; a batch is N=option, rest=option).",
        Answer,
        answer,
        False,
    ),
    _tool(
        "bot_run_wrong",
        "Correct a bot's gate",
        "A gate called the run (or one item) wrong: say what it should have said; it is learned as a precedent.",
        Wrong,
        wrong,
        False,
    ),
    _tool("bot_run_cancel", "Cancel a bot run", "End the run that waits on the person.", RunId, cancel, False),
    _tool(
        "bot_gates", "A bot's gates", "What its gates have learned: precedents, how often they ask.", Slug, gates, True
    ),
)
DETACHED: frozenset[str] = frozenset({"bot_run", "bot_run_answer", "bot_run_wrong", "bot_run_cancel", "bot_gates"})
