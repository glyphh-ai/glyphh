import uuid

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import invites, members, org
from glyphh_server.ops.invites import InviteView
from glyphh_server.ops.members import Member, MemberRole
from glyphh_server.ops.org import OrgView

router = APIRouter(prefix="/v1/org", tags=["org"])

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RenameOrg(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class MemberChange(BaseModel):
    role: MemberRole | None = None
    disabled: bool | None = None


class NewInvite(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=254)
    role: MemberRole = "user"


class CreatedInvite(BaseModel):
    invite: InviteView
    link: str = Field(description="The link to send the person: shown once, never stored")


@router.get("", operation_id="getOrg")
async def get_org(caller: Caller, conn: Conn) -> OrgView:
    return await org.get_org(conn, caller)


@router.patch("", operation_id="renameOrg")
async def rename_org(body: RenameOrg, caller: Caller, conn: Conn) -> OrgView:
    return await org.rename_org(conn, caller, body.name)


@router.get("/members", operation_id="listMembers")
async def list_members(caller: Caller, conn: Conn) -> list[Member]:
    return await members.list_members(conn, caller)


@router.patch("/members/{member_id}", operation_id="updateMember")
async def update_member(member_id: uuid.UUID, body: MemberChange, caller: Caller, conn: Conn) -> Member:
    return await members.update_member(conn, caller, member_id, body.role, body.disabled)


@router.delete("/members/{member_id}", operation_id="removeMember", status_code=204)
async def remove_member(member_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    await members.remove_member(conn, caller, member_id)
    return Response(status_code=204)


@router.get("/invites", operation_id="listInvites")
async def list_invites(caller: Caller, conn: Conn) -> list[InviteView]:
    return await invites.list_invites(conn, caller)


@router.post("/invites", operation_id="createInvite", status_code=201)
async def create_invite(body: NewInvite, request: Request, caller: Caller, conn: Conn) -> CreatedInvite:
    view, token = await invites.create_invite(conn, caller, body.email, body.role)
    base = request.app.state.settings.public_url.rstrip("/")
    return CreatedInvite(invite=view, link=f"{base}/auth/join?invite={token}")


@router.delete("/invites/{invite_id}", operation_id="revokeInvite", status_code=204)
async def revoke_invite(invite_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    await invites.revoke_invite(conn, caller, invite_id)
    return Response(status_code=204)
