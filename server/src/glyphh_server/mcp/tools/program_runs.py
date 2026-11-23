"""A program's runs over the connector (docs/specs/programs.md, 6). `run_program` starts one and follows it: each line
of its audit trail streamed as a progress notification while it goes (when the client asked for progress, api/
mcp_stream.py), up to two minutes; then it answers the run as it stands: done with its results, waiting with its
question, or still going with how to follow it. The runs' own tools: listed, read, answered, cancelled."""

import asyncio
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.db import tenancy
from glyphh_server.mcp.tools.base import Context, Done, Tool, dump
from glyphh_server.mcp.tools.programs import Slug
from glyphh_server.ops.programs import events, runs, store
from glyphh_server.ops.programs.views import EventView, ProgramRunView

FOLLOW: float = 120.0  # seconds run_program follows a run
EVERY: float = 1.0
LIVE: frozenset[str] = frozenset({"queued", "running", "dispatched"})
STOPS: frozenset[str] = frozenset({"asked", "done", "failed", "cancelled"})  # the trail's line of a run that stopped


class RunArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=1, max_length=80, description="The program's slug (programs lists them)")
    input: str = Field("", max_length=20_000, description="What the run is given: its steps read it as {input}")


class RunId(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: uuid.UUID


class Answer(RunId):
    answer: Any = Field(description="One of the question's options (for a bot's batch, N=option or a map)")


def said(e: EventView) -> str:
    who = f"({e.bot or e.by})" if e.bot or e.by else ""
    line = " ".join(part for part in (e.kind, e.step, who, e.title) if part)
    return f"{line}: {e.detail}" if e.detail else line


def run_line(run: ProgramRunView) -> str:
    if run.question:
        options = ", ".join(str(o) for o in run.question.get("options") or [])
        return f"Run {run.id} of {run.program} waits: {run.question.get('question')} ({options}); program_run_answer"
    if run.status in LIVE:
        return f"Run {run.id} of {run.program} is {run.status} at {run.at}: program_run_get follows it."
    if run.status == "failed":
        return f"Run {run.id} of {run.program} failed: {run.error}"
    return f"Run {run.id} of {run.program} is {run.status}. Results: {run.outputs}"[:2000]


async def _read(ctx: Context, run_id: uuid.UUID, after: int) -> tuple[ProgramRunView, list[EventView]]:
    async with ctx.bots.engine.begin() as conn:
        await tenancy.enter(conn, ctx.who.org_id)
        return runs.view(await runs.row(conn, run_id)), await events.read(conn, run_id, after)


async def follow(ctx: Context, run_id: uuid.UUID) -> tuple[ProgramRunView, list[EventView]]:
    """The run followed until it stops (its trail's line saying so read too) or FOLLOW seconds pass: it, and every
    line of its trail."""
    seen: list[EventView] = []
    waited = 0.0
    while True:
        run, new = await _read(ctx, run_id, seen[-1].n if seen else 0)
        for e in new:
            if ctx.progress is not None:
                await ctx.progress(said(e))
        seen += new
        stopped = run.status not in LIVE and bool(seen) and seen[-1].kind in STOPS
        if stopped or waited >= FOLLOW:
            return run, seen
        await asyncio.sleep(EVERY)
        waited += EVERY


async def run(ctx: Context, args: RunArgs) -> Done:
    made = await ctx.bots.programs.start(ctx.who, args.slug, args.input, "connector")
    shown, trail = await follow(ctx, made.id)
    lines = "\n".join(said(e) for e in trail)
    return Done(f"{lines}\n\n{run_line(shown)}".strip(), dump(shown) | {"events": [dump(e) for e in trail]})


async def list_runs(ctx: Context, args: Slug) -> Done:
    found = await runs.listed(ctx.conn, await store.row(ctx.conn, args.slug))
    return Done("\n".join(run_line(r) for r in found) or "No runs yet.", {"runs": [dump(r) for r in found]})


async def get_run(ctx: Context, args: RunId) -> Done:
    shown, trail = runs.view(await runs.row(ctx.conn, args.run_id)), await events.read(ctx.conn, args.run_id)
    text = "\n".join(said(e) for e in trail) + f"\n\n{run_line(shown)}"
    return Done(text.strip(), dump(shown) | {"events": [dump(e) for e in trail]})


async def answer(ctx: Context, args: Answer) -> Done:
    found = await ctx.bots.programs.answer(ctx.who, args.run_id, args.answer)
    return Done(f"Run {found.id} carries on: program_run_get follows it.", dump(found))


async def cancel(ctx: Context, args: RunId) -> Done:
    found = await ctx.bots.programs.cancel(ctx.who, args.run_id)
    return Done(f"Run {found.id} cancelled.", dump(found))


TOOLS: tuple[Tool, ...] = (
    Tool("run_program", "Run a program",
         "Run a program and follow it: each step streamed as it goes (up to two minutes), then the run as it stands: "
         "done with its results, waiting on the person with its question (program_run_answer), or still going "
         "(program_run_get).", RunArgs, run),
    Tool("program_runs", "A program's runs", "A program's runs, the newest first.", Slug, list_runs, read_only=True),
    Tool("program_run_get", "A program run", "One run: where it is, its results, its question, its audit trail.",
         RunId, get_run, read_only=True),
    Tool("program_run_answer", "Answer a program", "Answer the program run that waits on the person.", Answer, answer),
    Tool("program_run_cancel", "Cancel a program run", "A run stopped: it does not carry on.", RunId, cancel),
)  # fmt: skip
DETACHED: frozenset[str] = frozenset({"run_program", "program_run_answer", "program_run_cancel"})
STREAMED: frozenset[str] = frozenset({"run_program"})
