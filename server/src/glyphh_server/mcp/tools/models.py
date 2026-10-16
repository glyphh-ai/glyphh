"""The connector's model tools: the person's models, calling one on their runtime, answering a run and reading it.
Claude calls as the person (clearance 1, caller `claude`)."""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops import models, runs
from glyphh_server.ops.link.protocol import Name
from glyphh_server.ops.runs import RunView


class CallArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: Name = Field(description="The model's name")
    function: Name = Field("start", description="The function to call (glyphh.json names them)")
    inputs: dict[str, Any] = Field({}, description="The function's inputs")
    version: int | None = Field(None, ge=1, description="A version; default the one active on the runtime")
    runtime_id: uuid.UUID | None = Field(None, description="One of your runtimes; default the latest seen")


class ContinueArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID
    answer: Any = Field(None, description="The input the run waits for")


class RunArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID


def _run_line(run: RunView) -> str:
    when = f", {run.seconds}s" if run.seconds is not None else ""
    return f"{run.model} v{run.version} {run.function}: {run.status}{when} (run {run.id})"


async def models_list(ctx: Context, _: NoArgs) -> Done:
    found = await models.list_models(ctx.conn, ctx.who)
    lines = []
    for m in found:
        active = [v.version for v in m.versions if v.active_on]
        where = f"active v{', v'.join(map(str, active))}" if active else "not deployed"
        lines.append(f"{m.name}: {len(m.versions)} versions, {where}" + (f", {m.repo}" if m.repo else ""))
    return Done("\n".join(lines) or "You have no models.", {"models": [dump(m) for m in found]})


async def call(ctx: Context, args: CallArgs) -> Done:
    run = await runs.start_run(
        ctx.conn,
        ctx.hub,
        ctx.who,
        args.model,
        args.function,
        args.inputs,
        args.version,
        args.runtime_id,
        "claude",
        1.0,
    )
    return Done(_run_line(run) + "; call run_status for its result.", dump(run))


async def continue_(ctx: Context, args: ContinueArgs) -> Done:
    run = await runs.continue_run(ctx.conn, ctx.hub, ctx.who, args.run_id, args.answer)
    return Done(_run_line(run), dump(run))


async def run_status(ctx: Context, args: RunArgs) -> Done:
    run = await runs.get_run(ctx.conn, ctx.who, args.run_id)
    return Done(_run_line(run), dump(run))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "models_list",
        "Models",
        "Your models: each one's versions, and which is active on a runtime.",
        NoArgs,
        models_list,
        True,
    ),
    Tool(
        "call",
        "Call a model",
        "Call a function of one of your models on your runtime. The run starts; run_status shows its result.",
        CallArgs,
        call,
    ),
    Tool(
        "continue",
        "Continue a run",
        "Answer a run that is waiting for input.",
        ContinueArgs,
        continue_,
    ),
    Tool("run_status", "Run status", "What became of a run: its status and timing.", RunArgs, run_status, True),
)
