"""Where an MCP client finds the connector's authorization server: the protected resource's metadata (RFC 9728), at
the root and after /mcp's own path, and the authorization server's (RFC 8414)."""

from typing import Any

from fastapi import APIRouter, Request

from glyphh_server.models import AUTH_METHODS
from glyphh_server.ops.connector.authorize import SCOPE
from glyphh_server.ops.connector.clients import GRANT_TYPES

router = APIRouter(tags=["connector"])

RESOURCE_PATH: str = "/.well-known/oauth-protected-resource"


def resource_metadata_url(request: Request) -> str:
    return f"{request.app.state.settings.base_url}{RESOURCE_PATH}/mcp"


@router.get(RESOURCE_PATH, operation_id="protectedResourceMetadata")
@router.get(f"{RESOURCE_PATH}/mcp", operation_id="mcpProtectedResourceMetadata")
async def protected_resource(request: Request) -> dict[str, Any]:
    """The connector as an OAuth protected resource: what it is, and the authorization server that issues its
    tokens."""
    settings = request.app.state.settings
    return {
        "resource": settings.mcp_resource,
        "authorization_servers": [settings.base_url],
        "scopes_supported": [SCOPE],
        "bearer_methods_supported": ["header"],
        "resource_name": "Glyphh",
    }


@router.get("/.well-known/oauth-authorization-server", operation_id="authorizationServerMetadata")
async def authorization_server(request: Request) -> dict[str, Any]:
    """The connector's authorization server: its endpoints and what it supports (PKCE S256 only)."""
    base = request.app.state.settings.base_url
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "revocation_endpoint": f"{base}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": list(GRANT_TYPES),
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": list(AUTH_METHODS),
        "revocation_endpoint_auth_methods_supported": list(AUTH_METHODS),
        "scopes_supported": [SCOPE],
        "authorization_response_iss_parameter_supported": True,
    }
