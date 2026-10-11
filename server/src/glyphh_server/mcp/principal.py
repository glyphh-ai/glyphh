"""Who is calling an MCP tool: the member behind the bearer token the SDK already checked."""

import uuid

from mcp.server.auth.middleware.auth_context import get_access_token

from glyphh_server.errors import Unauthorized
from glyphh_server.obs import context
from glyphh_server.ops.auth.principal import Principal


def current_principal() -> Principal:
    token = get_access_token()
    if token is None or not token.subject or not token.claims:
        raise Unauthorized("Sign in to Glyphh first.")
    principal = Principal(
        user_id=uuid.UUID(token.subject), org_id=uuid.UUID(token.claims["org_id"]), role=token.claims["role"]
    )
    context.user_id.set(str(principal.user_id))
    context.org_id.set(str(principal.org_id))
    return principal
