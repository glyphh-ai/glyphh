import uuid

from fastapi import APIRouter, Response

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops.auth import hosts
from glyphh_server.ops.auth.hosts import Host
from glyphh_server.ops.me import Me, me

router = APIRouter(prefix="/v1/me", tags=["me"])


@router.get("", operation_id="me")
async def get_me(caller: Caller, conn: Conn) -> Me:
    return await me(conn, caller)


@router.get("/hosts", operation_id="listHosts")
async def list_hosts(caller: Caller, conn: Conn) -> list[Host]:
    """The agent hosts (Claude, Codex, ...) connected to my Glyphh."""
    return await hosts.connected(conn, caller.user_id)


@router.delete("/hosts/{host_id}", operation_id="disconnectHost", status_code=204)
async def disconnect_host(host_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    """Disconnect one host: its tokens stop working at once; the others are untouched."""
    await hosts.disconnect(conn, caller.user_id, host_id)
    return Response(status_code=204)
