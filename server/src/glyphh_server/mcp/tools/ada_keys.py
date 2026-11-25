"""The connector's API key tools: the keys the person's code calls Ada Cloud with (`glyphh_ak_…`,
docs/specs/ada-cloud.md, 4.1), made and shown once, listed, revoked; the same keys as the Ada API's /v1/keys."""

import uuid

from pydantic import BaseModel, ConfigDict

from glyphh_ada import keys
from glyphh_ada.api.keys import NewKey
from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump


class KeyId(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key_id: uuid.UUID


async def create(ctx: Context, args: NewKey) -> Done:
    made = await keys.create(ctx.conn, ctx.who, args.name.strip(), args.expires_in_days, args.clearance)
    expires = made.expires_at.date().isoformat() if made.expires_at else "never"
    text = (
        f"API key {made.name}: {made.key}\nShown once, expires {expires}, clearance {made.clearance:g}. Your code "
        f"sends it as `Authorization: Bearer <key>` to {ctx.settings.ada_base} (GLYPHH_API_KEY for the SDKs)."
    )
    return Done(text, dump(made))


async def listing(ctx: Context, _: NoArgs) -> Done:
    found = await keys.listing(ctx.conn, ctx.who)
    lines = [
        f"{k.name}, made {k.created_at:%Y-%m-%d}, clearance {k.clearance:g}"
        + (f", revoked {k.revoked_at:%Y-%m-%d}" if k.revoked_at else "")
        + f", id {k.id}"
        for k in found
    ]
    return Done("\n".join(lines) or "No API keys yet: create_api_key makes one.", {"keys": [dump(k) for k in found]})


async def revoke(ctx: Context, args: KeyId) -> Done:
    gone = await keys.revoke(ctx.conn, ctx.who, args.key_id)
    return Done(f"API key {gone.name} is revoked (within ten seconds everywhere).", dump(gone))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "create_api_key",
        "Create an API key",
        "A key for your code to call Ada Cloud with (the SDKs, or POST /v1/decide), in your org: shown once; it "
        "expires after the days given, or never; clearance (0 to 1) is what of a model's secured roles it may read.",
        NewKey,
        create,
    ),
    Tool(
        "api_keys",
        "API keys",
        "Your Ada Cloud API keys, live and revoked; never the keys themselves.",
        NoArgs,
        listing,
        True,
    ),
    Tool("revoke_api_key", "Revoke an API key", "Revoke one key (api_keys lists their ids).", KeyId, revoke),
)
