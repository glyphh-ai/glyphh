from mcp.server.mcpserver import MCPServer
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.mcp.guard import guarded
from glyphh_server.ops.health import Health, health


def register(mcp: MCPServer, engine: AsyncEngine, version: str) -> None:
    @mcp.tool(name="health", description="Is the Glyphh server up, and can it reach its database?")
    @guarded("health")
    async def health_tool() -> Health:
        return await health(engine, version)
