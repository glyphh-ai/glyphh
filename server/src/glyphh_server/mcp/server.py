"""MCP over Streamable HTTP, stateless: each call stands alone, so any process answers it.
Signed in with OAuth: Glyphh is the authorization server (mcp/oauth.py) and /mcp answers only a valid
bearer token. Tools are thin: each calls the same ops function the API route does."""

from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.applications import Starlette

from glyphh_server.config import Settings
from glyphh_server.mcp import health, me, org
from glyphh_server.mcp.oauth import GlyphhOAuth

# DNS-rebinding protection guards servers bound to localhost; this one is public, behind its own auth.
_PUBLIC: TransportSecuritySettings = TransportSecuritySettings(enable_dns_rebinding_protection=False)


def make_mcp(engine: AsyncEngine, settings: Settings) -> MCPServer:
    base = settings.public_url.rstrip("/")
    auth = AuthSettings(
        issuer_url=base,
        resource_server_url=f"{base}/mcp",
        validate_token_resource=False,
        client_registration_options=ClientRegistrationOptions(enabled=True),
        revocation_options=RevocationOptions(enabled=True),
    )
    provider = GlyphhOAuth(engine, settings.platform, settings.secret_key)
    mcp = MCPServer("glyphh", version=settings.version, auth=auth, auth_server_provider=provider)
    health.register(mcp, engine, settings.version)
    me.register(mcp, engine)
    org.register(mcp, engine, settings.platform)
    return mcp


def mcp_http_app(mcp: MCPServer) -> Starlette:
    return mcp.streamable_http_app(streamable_http_path="/mcp", stateless_http=True, transport_security=_PUBLIC)
