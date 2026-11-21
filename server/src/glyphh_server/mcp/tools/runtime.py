"""The connector's runtime key tools: the keys that call a self-hosted runtime at its own address. Calling a program is
not here: that is the runtime's own MCP, at its address, with one of these keys."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops import runtime_keys


class KeyName(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80, description="What the key is for: 'Claude', 'the CRM'")
    expires_in_days: int | None = Field(None, ge=1, le=365, description="Days until the key expires; left out, never")
    runtime_id: uuid.UUID = Field(description="The self-hosted runtime it calls (self_runtimes)")


class KeyId(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_id: uuid.UUID


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
        "runtime_keys",
        "Runtime keys",
        "The keys that call your self-hosted runtimes, live and revoked.",
        NoArgs,
        list_keys,
        True,
    ),
    Tool(
        "create_runtime_key",
        "Create a runtime key",
        "A new key for a self-hosted runtime's address (REST and MCP); shown once, it expires after the days given, or"
        " never.",
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
