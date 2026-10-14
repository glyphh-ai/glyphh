"""The signed-in person: who they are, their installs, signing out."""

import uuid

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import installs, me
from glyphh_server.ops.installs import InstallView
from glyphh_server.ops.me import Me

router = APIRouter(prefix="/v1", tags=["account"])


class Rename(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.get("/me", operation_id="me")
async def get_me(caller: Caller, conn: Conn) -> Me:
    """The user, their org and role, the plan version and its limits, and what is used."""
    return await me.me(conn, caller)


@router.patch("/me", operation_id="renameMe")
async def rename_me(body: Rename, caller: Caller, conn: Conn) -> Me:
    return await me.rename_me(conn, caller, body.name)


@router.get("/installs", operation_id="listInstalls")
async def list_installs(caller: Caller, conn: Conn) -> list[InstallView]:
    return await installs.list_installs(conn, caller)


@router.delete("/installs/{install_id}", operation_id="revokeInstall", status_code=204)
async def revoke_install(install_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    """Revoke one install: that machine is signed out."""
    await installs.revoke(conn, caller, install_id)
    return Response(status_code=204)


@router.post("/sign-out", operation_id="signOut", status_code=204)
async def sign_out(caller: Caller, conn: Conn) -> Response:
    """Revoke this install."""
    await installs.sign_out(conn, caller)
    return Response(status_code=204)
