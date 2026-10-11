from mcp.server.mcpserver import MCPServer
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.mcp.guard import guarded
from glyphh_server.mcp.principal import current_principal
from glyphh_server.ops.me import Me, me


def register(mcp: MCPServer, engine: AsyncEngine) -> None:
    @mcp.tool(name="me", description="Who am I signed in as in Glyphh: my profile, my role, my org and its plan.")
    @guarded("me")
    async def me_tool() -> Me:
        principal = current_principal()
        async with engine.connect() as conn:
            return await me(conn, principal)
