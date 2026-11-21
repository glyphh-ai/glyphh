"""The person's installs (signing one out), the org's members and open invites, and inviting someone."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.mcp.tools.base import Context, Done, NoArgs, Tool, dump
from glyphh_server.ops import installs, invites, members

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class InstallArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    install_id: uuid.UUID


class InviteArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(pattern=EMAIL, max_length=254)


async def list_installs(ctx: Context, _: NoArgs) -> Done:
    found = await installs.list_installs(ctx.conn, ctx.who)
    lines = [f"{i.name} ({i.surface}, mod {i.mod_version}), id {i.id}" for i in found] or ["No installs."]
    return Done("\n".join(lines), {"installs": [dump(i) for i in found]})


async def sign_out_install(ctx: Context, args: InstallArgs) -> Done:
    await installs.revoke(ctx.conn, ctx.who, args.install_id)
    return Done("That machine is signed out of Glyphh.", {"signed_out": str(args.install_id)})


async def list_members(ctx: Context, _: NoArgs) -> Done:
    people = await members.list_members(ctx.conn, ctx.who)
    waiting = await invites.list_invites(ctx.conn, ctx.who)
    lines = [f"{m.name or m.email} ({m.email}), {m.role}" for m in people]
    lines += [f"Invited: {i.email}, until {i.expires_at:%Y-%m-%d}" for i in waiting]
    return Done("\n".join(lines), {"members": [dump(m) for m in people], "invites": [dump(i) for i in waiting]})


async def invite(ctx: Context, args: InviteArgs) -> Done:
    view, token = await invites.create_invite(ctx.conn, ctx.who, args.email)
    link = f"{ctx.settings.invite_base}?invite={token}"
    return Done(f"Invited {view.email}. Send them this link (shown once): {link}", {"invite": dump(view), "link": link})


TOOLS: tuple[Tool, ...] = (
    Tool("installs", "Installs", "The machines signed in to Glyphh as you.", NoArgs, list_installs, True),
    Tool(
        "sign_out_install",
        "Sign out an install",
        "Sign one machine out of Glyphh (installs lists their ids).",
        InstallArgs,
        sign_out_install,
    ),
    Tool("members", "Members", "The org's members and its open invites.", NoArgs, list_members, True),
    Tool(
        "invite",
        "Invite",
        "Invite someone to the org by email; answers the link to send them. Only the org's admin can.",
        InviteArgs,
        invite,
    ),
)
