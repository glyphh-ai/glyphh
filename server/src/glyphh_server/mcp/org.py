"""The org's tools for agents: the same operations as /v1/org, one tool each."""

import uuid

from mcp.server.mcpserver import MCPServer
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.mcp.guard import guarded
from glyphh_server.mcp.principal import current_principal
from glyphh_server.ops import invites, members, org
from glyphh_server.ops.invites import InviteView
from glyphh_server.ops.members import Member, MemberRole
from glyphh_server.ops.org import OrgView


def register(mcp: MCPServer, engine: AsyncEngine, platform: str) -> None:
    @mcp.tool(name="org", description="My org in Glyphh: its name, plan, and how many seats are taken.")
    @guarded("org")
    async def org_tool() -> OrgView:
        async with engine.connect() as conn:
            return await org.get_org(conn, current_principal())

    @mcp.tool(name="members", description="The people in my org: role, and whether each is disabled.")
    @guarded("members")
    async def members_tool() -> list[Member]:
        async with engine.connect() as conn:
            return await members.list_members(conn, current_principal())

    @mcp.tool(
        name="invite",
        description="Invite someone into my org by email (org admins only). Answers the "
        "link to send them; it works once and expires in 7 days.",
    )
    @guarded("invite")
    async def invite_tool(email: str, role: MemberRole = "user") -> dict[str, object]:
        async with engine.begin() as conn:
            view, token = await invites.create_invite(conn, current_principal(), email, role)
        return {"invite": view.model_dump(mode="json"), "link": f"{platform}/join?invite={token}"}

    @mcp.tool(name="invites", description="My org's open invites (org admins only).")
    @guarded("invites")
    async def invites_tool() -> list[InviteView]:
        async with engine.connect() as conn:
            return await invites.list_invites(conn, current_principal())

    @mcp.tool(name="revoke_invite", description="Withdraw an open invite (org admins only); its seat is freed.")
    @guarded("revoke_invite")
    async def revoke_tool(invite_id: uuid.UUID) -> str:
        async with engine.begin() as conn:
            await invites.revoke_invite(conn, current_principal(), invite_id)
        return "Withdrawn."
