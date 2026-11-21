"""The connector's self-hosted runtime tools: the person's runtimes on their own infrastructure listed (each with
the address Claude connects to it at, and whether its release keeps the graph), one registered (its token and
environment shown once), and an offline licence issued for one that is air-gapped. A rrotor's own work (programs,
pipelines, the graph, the secrets form) is never done here: Glyphh's server is not on that path."""

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


GRAPH_FROM: tuple[int, ...] = (0, 4, 0)  # the rrotor release with the graph and the secrets form
CONNECT: str = (
    "A rrotor is its own connector: its programs, CLIs, apps, pipelines, graph (graph_schema, graph_search) and the "
    "secrets form (secrets_form) are its own tools, reached at its mcp_url, never through Glyphh. If those tools are "
    "not in this conversation, the person adds that address to Claude as a connector (signing in to Glyphh)."
)


def has_graph(version: str | None) -> bool | None:
    """Whether a rrotor of this version keeps the graph (0.4.0 on); None when it has not said its version, or said
    one that is no release number."""
    parts = (version or "").split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts) >= GRAPH_FROM


def _said(version: str | None) -> str:
    if not version:
        return ""
    old = ": before 0.4.0, no graph or secrets form until it is updated" if has_graph(version) is False else ""
    return f", rrotor {version}{old}"


async def list_self(ctx: Context, _: NoArgs) -> Done:
    found = await self_hosted.list_self(ctx.conn, ctx.who)
    lines = [
        f"{r.name} at {r.public_url}: {r.state}"
        + _said(r.version)
        + (f", last heartbeat {r.last_heartbeat_at:%Y-%m-%d %H:%M} UTC" if r.last_heartbeat_at else "")
        + f", id {r.id}; Claude connects to it at {r.public_url}/mcp"
        for r in found
    ]
    text = "\n".join([*lines, CONNECT]) if lines else "No self-hosted runtimes yet: register_self_runtime adds one."
    runtimes = [{**dump(r), "mcp_url": f"{r.public_url}/mcp", "graph": has_graph(r.version)} for r in found]
    return Done(text, {"runtimes": runtimes, "connect": CONNECT})


async def register(ctx: Context, args: NewSelf) -> Done:
    made = await self_hosted.register(ctx.conn, ctx.settings, ctx.who, args.name.strip(), args.public_url)
    env = "\n".join(f"{k}={v}" for k, v in made.env.items())
    text = f"Self-hosted runtime {made.name} registered at {made.public_url}. Its environment, shown once:\n{env}\n"
    text += f"Add it to Claude as a connector at {made.public_url}/mcp."
    return Done(text, {**dump(made), "mcp_url": f"{made.public_url}/mcp"})


async def offline_licence(ctx: Context, args: OfflineFor) -> Done:
    issued = await heartbeat.offline(ctx.conn, ctx.signing_key, ctx.who, args.runtime_id, args.days)
    text = f"Offline licence, expires {issued.expires_at:%Y-%m-%d} (14 days' grace after):\n{issued.token}\n"
    text += "Set it as RROTOR_LICENCE, or write it to /data/licence.token."
    return Done(text, dump(issued))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "self_runtimes",
        "Self-hosted runtimes",
        "Your runtimes on your own infrastructure: address, state, version and last heartbeat, the address Claude "
        "connects to each at (mcp_url: its own connector, with its programs, pipelines, graph and secrets form) and "
        "whether it keeps the graph (rrotor 0.4.0 on).",
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
