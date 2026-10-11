"""MCP over Streamable HTTP, stateless: each call stands alone, so any process answers it."""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.applications import Starlette

from glyphh_server.ops.health import Health, health

# DNS-rebinding protection guards servers bound to localhost; this one is public, behind its own auth.
_PUBLIC: TransportSecuritySettings = TransportSecuritySettings(enable_dns_rebinding_protection=False)


def make_mcp(engine: AsyncEngine, version: str) -> MCPServer:
    mcp: MCPServer = MCPServer("glyphh", version=version)

    @mcp.tool(name="health", description="Is the Glyphh server up, and can it reach its database?")
    async def health_tool() -> Health:
        return await health(engine, version)

    return mcp


def mcp_http_app(mcp: MCPServer) -> Starlette:
    return mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, transport_security=_PUBLIC)
