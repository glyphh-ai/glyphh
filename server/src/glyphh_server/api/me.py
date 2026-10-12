import uuid

from fastapi import APIRouter, Response

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops.auth import hosts
from glyphh_server.ops.auth.hosts import Host
from glyphh_server.ops.me import Me, MeOrg, me, my_orgs
from glyphh_server.ops.settings import Settings, SettingsChange, change_settings, settings_of

router = APIRouter(prefix="/v1/me", tags=["me"])


@router.get("", operation_id="me")
async def get_me(caller: Caller, conn: Conn) -> Me:
    return await me(conn, caller)


@router.get("/orgs", operation_id="listMyOrgs")
async def list_my_orgs(caller: Caller, conn: Conn) -> list[MeOrg]:
    """Every org I belong to, my Personal org first."""
    return await my_orgs(conn, caller.user_id)


@router.get("/settings", operation_id="mySettings")
async def my_settings(caller: Caller, conn: Conn) -> Settings:
    """What the platform remembers for me: the theme, the rail, each list's rows per page."""
    return await settings_of(conn, caller.user_id)


@router.patch("/settings", operation_id="changeMySettings")
async def change_my_settings(body: SettingsChange, caller: Caller, conn: Conn) -> Settings:
    """Change any of them; a list's rows per page are merged in by the list's name."""
    return await change_settings(conn, caller.user_id, body)


@router.get("/hosts", operation_id="listHosts")
async def list_hosts(caller: Caller, conn: Conn) -> list[Host]:
    """The agent hosts (Claude, Codex, ...) connected to my Glyphh."""
    return await hosts.connected(conn, caller.user_id)


@router.delete("/hosts/{host_id}", operation_id="disconnectHost", status_code=204)
async def disconnect_host(host_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    """Disconnect one host: its tokens stop working at once; the others are untouched."""
    await hosts.disconnect(conn, caller.user_id, host_id)
    return Response(status_code=204)
