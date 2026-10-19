"""The connector's self-hosted runtime tools: the person's runtimes on their own infrastructure listed, one
registered (its token and environment shown once), and an offline licence issued for one that is air-gapped."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops import heartbeat, self_hosted


class NewSelf(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80, pattern=r"\S", description="What it is called: 'Acme prod'")
    public_url: str = Field(min_length=1, max_length=300, description="https://<host> it answers at, no path")


class OfflineFor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runtime_id: uuid.UUID
    days: int = Field(ge=1, le=365, description="How long the licence lasts, 1 to 365 days")


async def list_self(ctx: Context, _: NoArgs) -> Done:
    found = await self_hosted.list_self(ctx.conn, ctx.who)
    lines = [
        f"{r.name} at {r.public_url}: {r.state}"
        + (f", rrotor {r.version}" if r.version else "")
        + (f", last heartbeat {r.last_heartbeat_at:%Y-%m-%d %H:%M} UTC" if r.last_heartbeat_at else "")
        + f", id {r.id}"
        for r in found
    ]
    text = "\n".join(lines) or "No self-hosted runtimes yet: register_self_runtime adds one."
    return Done(text, {"runtimes": [dump(r) for r in found]})


async def register(ctx: Context, args: NewSelf) -> Done:
    made = await self_hosted.register(ctx.conn, ctx.settings, ctx.who, args.name.strip(), args.public_url)
    env = "\n".join(f"{k}={v}" for k, v in made.env.items())
    text = f"Self-hosted runtime {made.name} registered at {made.public_url}. Its environment, shown once:\n{env}\n"
    text += f"Add it to Claude as a connector at {made.public_url}/mcp."
    return Done(text, dump(made))


async def offline_licence(ctx: Context, args: OfflineFor) -> Done:
    issued = await heartbeat.offline(ctx.conn, ctx.signing_key, ctx.who, args.runtime_id, args.days)
    text = f"Offline licence, expires {issued.expires_at:%Y-%m-%d} (14 days' grace after):\n{issued.token}\n"
    text += "Set it as RROTOR_LICENCE, or write it to /data/licence.token."
    return Done(text, dump(issued))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "self_runtimes",
        "Self-hosted runtimes",
        "Your runtimes on your own infrastructure: address, state, version and last heartbeat.",
        NoArgs,
        list_self,
        True,
    ),
    Tool(
        "register_self_runtime",
        "Register a self-hosted runtime",
        "Register a rrotor you run yourself (Docker Compose, Helm, Terraform) at its public https address: its token"
        " and environment, shown once.",
        NewSelf,
        register,
    ),
    Tool(
        "offline_licence",
        "Issue an offline licence",
        "A licence of 1 to 365 days for an air-gapped self-hosted runtime (self_runtimes lists their ids): on "
        "Enterprise only.",
        OfflineFor,
        offline_licence,
    ),
)
