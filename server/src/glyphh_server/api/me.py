"""The signed-in person: who they are. The platform reads it for the name it shows and to open its staff view."""

from fastapi import APIRouter, Request

from glyphh_server.admin.staff import is_staff
from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import me
from glyphh_server.ops.me import Me

router = APIRouter(prefix="/v1", tags=["account"])


@router.get("/me", operation_id="me")
async def get_me(caller: Caller, conn: Conn, request: Request) -> Me:
    """The person, the providers they sign in with, their org and role, and whether they are Glyphh's staff."""
    return await me.me(conn, caller, is_staff(request.app.state.settings, caller))
