"""The connector's grants, from the account: each client the person allowed, and revoking one."""

import uuid

from fastapi import APIRouter, Response

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops.connector import grants
from glyphh_server.ops.connector.grants import GrantView

router = APIRouter(prefix="/v1/connector", tags=["connector"])


@router.get("/grants", operation_id="listConnectorGrants")
async def list_grants(caller: Caller, conn: Conn) -> list[GrantView]:
    """Each client allowed to use the Glyphh connector as you: its name, scope, when allowed and last used."""
    return await grants.list_grants(conn, caller)


@router.delete("/grants/{grant_id}", operation_id="revokeConnectorGrant", status_code=204)
async def revoke_grant(grant_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    """Revoke one grant: its client is signed out and every token it holds stops working."""
    await grants.revoke(conn, caller, grant_id)
    return Response(status_code=204)
