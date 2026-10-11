"""MCP over Streamable HTTP, stateless: each call stands alone, so any process answers it.
Tools are thin: each calls the same ops function the API route does."""

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.applications import Starlette

from glyphh_server.mcp import health

# DNS-rebinding protection guards servers bound to localhost; this one is public, behind its own auth.
_PUBLIC: TransportSecuritySettings = TransportSecuritySettings(enable_dns_rebinding_protection=False)


def make_mcp(engine: AsyncEngine, version: str) -> MCPServer:
    mcp = MCPServer("glyphh", version=version)
    health.register(mcp, engine, version)
    return mcp


def mcp_http_app(mcp: MCPServer) -> Starlette:
    return mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, transport_security=_PUBLIC)
