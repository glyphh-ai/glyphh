"""The signed-in person answers an invite sent to them: accept (they join, keeping every other org) or decline."""

from fastapi import APIRouter, Response
from pydantic import BaseModel

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import invites

router = APIRouter(prefix="/v1/invites", tags=["invites"])


class InviteAnswer(BaseModel):
    invite: str


class Joined(BaseModel):
    org: str


@router.post("/accept", operation_id="acceptInvite")
async def accept(body: InviteAnswer, caller: Caller, conn: Conn) -> Joined:
    return Joined(org=await invites.accept_invite(conn, body.invite, caller.user_id))


@router.post("/decline", operation_id="declineInvite", status_code=204)
async def decline(body: InviteAnswer, caller: Caller, conn: Conn) -> Response:
    await invites.decline_invite(conn, body.invite, caller.user_id)
    return Response(status_code=204)
