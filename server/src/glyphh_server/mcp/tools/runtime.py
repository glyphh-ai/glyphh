"""The connector's runtime tools: the person's first hosted machine (its address, state and the month's online
time), starting and stopping it or another machine named by id, and the keys that call them. Calling a model is not
here: that is the runtime's own MCP, at its address, with one of these keys."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.mcp.tools.machines import line
from glyphh_server.ops import machines, runtime_keys, runtimes
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.runtimes import HostedRuntime


class KeyName(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80, description="What the key is for: 'Claude', 'the CRM'")
    expires_in_days: int | None = Field(None, ge=1, le=365, description="Days until the key expires; left out, never")
    runtime_id: uuid.UUID | None = Field(
        None,
        description="A hosted machine (runtimes) or self-hosted runtime (self_runtimes); left out, every hosted one",
    )


class MaybeMachine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID | None = Field(None, description="A machine's id (runtimes); left out, your first machine")


class KeyId(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_id: uuid.UUID


def _line(view: HostedRuntime) -> str:
    if view.runtime_id is None:
        return "You have no hosted runtime yet: start_runtime makes one."
    hours = f"{view.seconds_used / 3600:.1f} h this month"
    return f"Your runtime is {view.state} at {view.address}, {hours}."


async def runtime(ctx: Context, _: NoArgs) -> Done:
    view = await runtimes.hosted_view(ctx.conn, ctx.who, ctx.settings.fly_public_domain)
    return Done(_line(view), dump(view))


async def start_runtime(ctx: Context, args: MaybeMachine) -> Done:
    fly, connect = Fly(ctx.http, ctx.settings), " Add it to Claude as a connector: its /mcp, with a runtime key."
    if args.id is not None:
        started = await machines.start(ctx.conn, fly, ctx.who, args.id)
        return Done(line(started) + "." + connect, dump(started))
    await machines.start_first(ctx.conn, fly, ctx.who)
    view = await runtimes.hosted_view(ctx.conn, ctx.who, ctx.settings.fly_public_domain)
    return Done(_line(view) + connect, dump(view))


async def stop_runtime(ctx: Context, args: MaybeMachine) -> Done:
    fly = Fly(ctx.http, ctx.settings)
    if args.id is not None:
        stopped = await machines.stop(ctx.conn, fly, ctx.who, args.id)
        return Done(line(stopped) + ".", dump(stopped))
    await machines.stop(ctx.conn, fly, ctx.who, await machines.first(ctx.conn, ctx.who))
    view = await runtimes.hosted_view(ctx.conn, ctx.who, ctx.settings.fly_public_domain)
    return Done(_line(view), dump(view))


async def list_keys(ctx: Context, _: NoArgs) -> Done:
    found = await runtime_keys.list_keys(ctx.conn, ctx.who)
    lines = [
        f"{k.name}, made {k.created_at:%Y-%m-%d}"
        + (f", revoked {k.revoked_at:%Y-%m-%d}" if k.revoked_at else "")
        + f", {k.calls} calls"
        + f", id {k.id}"
        for k in found
    ]
    return Done("\n".join(lines) or "No runtime keys yet.", {"keys": [dump(k) for k in found]})


async def create_key(ctx: Context, args: KeyName) -> Done:
    days, target = args.expires_in_days, args.runtime_id
    made = await runtime_keys.create_key(ctx.conn, ctx.hub, ctx.who, args.name.strip(), days, target)
    expires = made.expires_at.date().isoformat() if made.expires_at else "never"
    text = f"Runtime key {made.name}: {made.key}\nShown once, expires {expires}."
    text += " Use it as the bearer at your runtime's address."
    return Done(text, dump(made))


async def revoke_key(ctx: Context, args: KeyId) -> Done:
    gone = await runtime_keys.revoke_key(ctx.conn, ctx.hub, ctx.who, args.key_id)
    return Done(f"Runtime key {gone.name} is revoked.", dump(gone))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "runtime",
        "Runtime",
        "Your first hosted machine: its address, state and the month's online time.",
        NoArgs,
        runtime,
        True,
    ),
    Tool(
        "start_runtime",
        "Start the runtime",
        "Start a hosted machine by id, or your first (made the first time). Its models are then called at its own"
        " address.",
        MaybeMachine,
        start_runtime,
    ),
    Tool(
        "stop_runtime",
        "Stop the runtime",
        "Stop a hosted machine by id, or your first, now; a call starts it again.",
        MaybeMachine,
        stop_runtime,
    ),
    Tool("runtime_keys", "Runtime keys", "The keys that call your runtime, live and revoked.", NoArgs, list_keys, True),
    Tool(
        "create_runtime_key",
        "Create a runtime key",
        "A new key for a runtime's address (REST and MCP): one hosted machine or self-hosted runtime, or every"
        " hosted machine of yours; shown once, it expires after the days given, or never.",
        KeyName,
        create_key,
    ),
    Tool(
        "revoke_runtime_key",
        "Revoke a runtime key",
        "Revoke one key (runtime_keys lists their ids).",
        KeyId,
        revoke_key,
    ),
)
