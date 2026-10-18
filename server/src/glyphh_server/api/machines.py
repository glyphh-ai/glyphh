"""The person's hosted machines: listed, made (named, of a size) and started, shown, started, stopped, restarted and
deleted, each only by its owner (404 for anyone else's). Self-hosted runtimes are under /v1/runtimes/self."""

import uuid

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.api.runtime import fly
from glyphh_server.models.rrotor import SIZES_SAID, SizeName
from glyphh_server.ops import machines
from glyphh_server.ops.machines import Machine

router = APIRouter(prefix="/v1/runtimes", tags=["runtime"])


class NewMachine(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S", description="What the machine is called")
    size: SizeName = Field(description=SIZES_SAID)


def _domain(request: Request) -> str:
    return str(request.app.state.settings.fly_public_domain)


@router.get("", operation_id="listMachines")
async def list_machines(caller: Caller, conn: Conn, request: Request) -> list[Machine]:
    """Your hosted machines, oldest first: each one's size, state, address and online time this month."""
    return await machines.list_machines(conn, caller, _domain(request))


@router.post("", operation_id="createMachine", status_code=201)
async def create_machine(body: NewMachine, caller: Caller, conn: Conn, request: Request) -> Machine:
    """A new hosted machine, made and started; past your plan's machines E_LIMIT `machines`, a name you have used
    E_CONFLICT `name`."""
    return await machines.create(conn, fly(request), caller, body.name.strip(), body.size)


@router.get("/{runtime_id}", operation_id="machine")
async def machine(runtime_id: uuid.UUID, caller: Caller, conn: Conn, request: Request) -> Machine:
    """One of your hosted machines."""
    return await machines.machine(conn, caller, runtime_id, _domain(request))


@router.post("/{runtime_id}/start", operation_id="startMachine")
async def start_machine(runtime_id: uuid.UUID, caller: Caller, conn: Conn, request: Request) -> Machine:
    """Start the machine; it is `stopped` until its rrotor links, `online` then."""
    return await machines.start(conn, fly(request), caller, runtime_id)


@router.post("/{runtime_id}/stop", operation_id="stopMachine")
async def stop_machine(runtime_id: uuid.UUID, caller: Caller, conn: Conn, request: Request) -> Machine:
    """Stop the machine now (it stops by itself when idle; a call to its address starts it again)."""
    return await machines.stop(conn, fly(request), caller, runtime_id)


@router.post("/{runtime_id}/restart", operation_id="restartMachine")
async def restart_machine(runtime_id: uuid.UUID, caller: Caller, conn: Conn, request: Request) -> Machine:
    """Restart the machine: its rrotor starts again and links again."""
    return await machines.restart(conn, fly(request), caller, runtime_id)


@router.delete("/{runtime_id}", operation_id="deleteMachine", status_code=204)
async def delete_machine(
    runtime_id: uuid.UUID, caller: Caller, conn: Conn, request: Request, confirm: str = ""
) -> Response:
    """Delete the machine: the machine, its disk and every model, version, precedent and file on it. `confirm` must
    be its name (else E_INVALID `confirm`). Fly keeps daily snapshots for 5 days; Glyphh keeps no other backup."""
    await machines.destroy(conn, fly(request), caller, runtime_id, confirm)
    return Response(status_code=204)
