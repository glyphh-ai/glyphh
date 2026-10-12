import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops.machines.cards import MachinePage, list_machines
from glyphh_server.ops.machines.installed import InstalledPage, installed
from glyphh_server.ops.machines.launch import Launch, open_machine

router = APIRouter(prefix="/v1/machines", tags=["machines"])
Page = Annotated[int, Query(ge=1)]
Size = Annotated[int, Query(ge=1, le=100)]
Status = Literal["working", "thinking", "needs_you", "idle", "stuck", "done"]


class OpenIn(BaseModel):
    super_power: uuid.UUID | None = None


@router.get("", operation_id="listMachines")
async def machines(caller: Caller, conn: Conn, page: Page = 1, size: Size = 12) -> MachinePage:
    """My machines, connected first, each with its 8 most recently active super powers."""
    return await list_machines(conn, caller, page, size)


@router.get("/{machine_id}/super-powers", operation_id="listInstalledSuperPowers")
async def super_powers(
    machine_id: uuid.UUID,
    caller: Caller,
    conn: Conn,
    q: Annotated[str, Query(max_length=200)] = "",
    status: Status | None = None,
    page: Page = 1,
    size: Size = 24,
) -> InstalledPage:
    """Every super power on one of my machines, searched and filtered, with how many of each status."""
    return await installed(conn, caller, machine_id, q.strip(), status, page, size)


@router.post("/{machine_id}/open", operation_id="openMachine")
async def open_one(machine_id: uuid.UUID, body: OpenIn, caller: Caller, conn: Conn, request: Request) -> Launch:
    """A one-minute, one-time link into the machine's UI, on its home or one of its super powers."""
    domain = request.app.state.settings.machines_domain
    return await open_machine(conn, caller, machine_id, body.super_power, domain)
