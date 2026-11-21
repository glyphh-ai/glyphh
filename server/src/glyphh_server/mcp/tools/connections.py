"""The org's connections to other services, for its bots (docs/specs/bots.md): listing them, the services there are,
a link to sign in to one for the org, and what a bot may be let do with one. The ones that call Pipedream run with no
request transaction (registry.DETACHED)."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.errors import Unavailable
from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops.bots import connections
from glyphh_server.ops.bots.connviews import LinkIn, PermissionsIn
from glyphh_server.ops.bots.pipedream import OFF, Pipedream


class AppsArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str | None = Field(None, max_length=200, description="Matches the service's name")
    cursor: str | None = Field(None, max_length=500, description="next_cursor of the page before")


class ConnectionArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: uuid.UUID = Field(description="The connection (connections lists them)")


def pipedream(ctx: Context) -> Pipedream:
    pd: Pipedream = ctx.bots.pd
    if not pd.on:
        raise Unavailable(OFF, reason="pipedream_off")
    return pd


async def list_connections(ctx: Context, _: NoArgs) -> Done:
    found = await connections.sync(pipedream(ctx), ctx.bots.engine, ctx.who)
    lines = [f"{c.app_name} {c.label} (id {c.id})".replace("  ", " ") for c in found]
    return Done("\n".join(lines) or "The org has no connections yet.", {"connections": [dump(c) for c in found]})


async def list_apps(ctx: Context, args: AppsArgs) -> Done:
    found = await connections.apps(pipedream(ctx), args.q, args.cursor)
    lines = [f"{a.name} ({a.slug}): {a.description}"[:200] for a in found.apps]
    return Done("\n".join(lines) or "No such service.", dump(found))


async def link(ctx: Context, args: LinkIn) -> Done:
    made = await connections.link(pipedream(ctx), ctx.who, args.app)
    said = f"Open this to sign in to {args.app} for the org, then call connections: {made.url}"
    return Done(said, dump(made))


async def list_tools(ctx: Context, args: ConnectionArgs) -> Done:
    found = await connections.tools(pipedream(ctx), ctx.bots.engine, ctx.who, args.connection_id)
    lines = [f"{t.key}: {t.name} ({t.permission})" for t in found]
    return Done("\n".join(lines) or "It has no tools.", {"tools": [dump(t) for t in found]})


class Permissions(PermissionsIn, ConnectionArgs):
    pass


async def set_permissions(ctx: Context, args: Permissions) -> Done:
    found = await connections.set_permissions(ctx.conn, args.connection_id, PermissionsIn(permissions=args.permissions))
    said = ", ".join(f"{k} {v}" for k, v in sorted(args.permissions.items()))
    return Done(f"{found.app_name} {found.label}: {said}.".replace("  ", " "), dump(found))


TOOLS: tuple[Tool, ...] = (
    Tool(
        "connections",
        "Connections",
        "The org's connections to other services (Gmail, Slack, ...) that its bots can use, brought up to date with "
        "the accounts signed in since.",
        NoArgs,
        list_connections,
        True,
    ),
    Tool(
        "connection_apps",
        "Services to connect",
        "The services a connection can be made to, by name; each one's slug is what connection_link takes.",
        AppsArgs,
        list_apps,
        True,
    ),
    Tool(
        "connection_link",
        "Connect a service",
        "A link where the person signs in to a service for the org (Pipedream's page; Glyphh keeps no sign-in). "
        "Give it to them to open; once they have, connections lists the new connection.",
        LinkIn,
        link,
    ),
    Tool(
        "connection_tools",
        "A connection's tools",
        "What a bot may be let do with a connection: each tool's key, as bot_connections_set takes it, and its "
        "permission (allow, ask or deny).",
        ConnectionArgs,
        list_tools,
        True,
    ),
    Tool(
        "connection_permissions_set",
        "Set a connection's tool permissions",
        "Per tool key, what the org's bots may do with it: allow, ask (a step that uses it waits for the person's yes, "
        "in the approvals queue) or deny. A tool never set asks. Keys not named keep what they had.",
        Permissions,
        set_permissions,
    ),
)
DETACHED: frozenset[str] = frozenset(t.name for t in TOOLS) - {"connection_permissions_set"}
