"""The connector's runtime tools: the person's hosted runtime (its address, state and the month's hours), starting
and stopping it, and the keys that call it. Calling a model is not here: that is the runtime's own MCP, at its
address, with one of these keys."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops import hosted, runtime_keys, runtimes
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.runtimes import HostedRuntime


class KeyName(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80, description="What the key is for: 'Claude', 'the CRM'")


class KeyId(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_id: uuid.UUID


def _line(view: HostedRuntime) -> str:
    if view.runtime_id is None:
        return "You have no hosted runtime yet: start_runtime makes one."
    allowed = "unlimited" if view.hours_allowed is None else f"of {view.hours_allowed}"
    hours = f"{view.seconds_used / 3600:.1f} h {allowed} this month"
    paused = "; paused: the month's hours are spent" if view.paused else ""
    return f"Your runtime is {view.state} at {view.address}, {hours}{paused}."


async def runtime(ctx: Context, _: NoArgs) -> Done:
    view = await runtimes.hosted_view(ctx.conn, ctx.who, ctx.settings.fly_public_domain)
    return Done(_line(view), dump(view))


async def start_runtime(ctx: Context, _: NoArgs) -> Done:
    view = await hosted.start_hosted(ctx.conn, Fly(ctx.http, ctx.settings), ctx.settings, ctx.who)
    return Done(_line(view) + " Add it to Claude as a connector: its /mcp, with a runtime key.", dump(view))


async def stop_runtime(ctx: Context, _: NoArgs) -> Done:
    view = await hosted.stop_hosted(ctx.conn, Fly(ctx.http, ctx.settings), ctx.who, ctx.settings.fly_public_domain)
    return Done(_line(view), dump(view))


async def list_keys(ctx: Context, _: NoArgs) -> Done:
    found = await runtime_keys.list_keys(ctx.conn, ctx.who)
    lines = [
        f"{k.name}, made {k.created_at:%Y-%m-%d}"
        + (f", revoked {k.revoked_at:%Y-%m-%d}" if k.revoked_at else "")
        + f", id {k.id}"
        for k in found
    ]
    return Done("\n".join(lines) or "No runtime keys yet.", {"keys": [dump(k) for k in found]})


async def create_key(ctx: Context, args: KeyName) -> Done:
    made = await runtime_keys.create_key(ctx.conn, ctx.hub, ctx.who, args.name.strip())
    text = f"Runtime key {made.name}: {made.key}\nShown once. Use it as the bearer at your runtime's address."
    return Done(text, dump(made))


async def revoke_key(ctx: Context, args: KeyId) -> Done:
    gone = await runtime_keys.revoke_key(ctx.conn, ctx.hub, ctx.who, args.key_id)
    return Done(f"Runtime key {gone.name} is revoked.", dump(gone))


TOOLS: tuple[Tool, ...] = (
    Tool("runtime", "Runtime", "Your hosted runtime: its address, state and the month's hours.", NoArgs, runtime, True),
    Tool(
        "start_runtime",
        "Start the runtime",
        "Start your hosted runtime (made the first time). Its models are then called at its own address.",
        NoArgs,
        start_runtime,
    ),
    Tool(
        "stop_runtime",
        "Stop the runtime",
        "Stop your hosted runtime now; a call starts it again.",
        NoArgs,
        stop_runtime,
    ),
    Tool("runtime_keys", "Runtime keys", "The keys that call your runtime, live and revoked.", NoArgs, list_keys, True),
    Tool(
        "create_runtime_key",
        "Create a runtime key",
        "A new key for your runtime's address (REST and MCP), shown once.",
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
