"""The connector's own grants: each client allowed to use Glyphh as the person, and revoking one."""

import uuid

from pydantic import BaseModel, ConfigDict

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops.connector import grants


class GrantArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grant_id: uuid.UUID


async def list_grants(ctx: Context, _: NoArgs) -> Done:
    found = await grants.list_grants(ctx.conn, ctx.who)
    lines = [
        f"{g.client} ({'this one' if g.current else g.scope}), allowed {g.created_at:%Y-%m-%d}, id {g.id}"
        for g in found
    ]
    return Done("\n".join(lines), {"grants": [dump(g) for g in found]})


async def revoke_grant(ctx: Context, args: GrantArgs) -> Done:
    await grants.revoke(ctx.conn, ctx.who, args.grant_id)
    return Done("That client can no longer use your Glyphh account.", {"revoked": str(args.grant_id)})


TOOLS: tuple[Tool, ...] = (
    Tool(
        "connector_grants",
        "Connector grants",
        "The apps allowed to use your Glyphh account through this connector.",
        NoArgs,
        list_grants,
        True,
    ),
    Tool(
        "revoke_grant",
        "Revoke a grant",
        "Stop one app using your Glyphh account through this connector (connector_grants lists their ids).",
        GrantArgs,
        revoke_grant,
    ),
)
