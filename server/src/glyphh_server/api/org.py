"""The caller's org, its members and its invites. Writes are the admin's."""

import uuid

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import invites, joining, members, org, sso
from glyphh_server.ops.invites import InviteView
from glyphh_server.ops.joining import Joined
from glyphh_server.ops.members import Member
from glyphh_server.ops.org import OrgView
from glyphh_server.ops.sso import SsoIn, SsoView

router = APIRouter(prefix="/v1", tags=["org"])

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RenameOrg(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class NewInvite(BaseModel):
    email: str = Field(pattern=EMAIL, max_length=254)


class CreatedInvite(BaseModel):
    invite: InviteView
    link: str = Field(description="The link to share with the person: shown once, never stored")


class AcceptInvite(BaseModel):
    token: str = Field(min_length=1, max_length=200)


@router.get("/org", operation_id="getOrg")
async def get_org(caller: Caller, conn: Conn) -> OrgView:
    return await org.get_org(conn, caller)


@router.patch("/org", operation_id="renameOrg")
async def rename_org(body: RenameOrg, caller: Caller, conn: Conn) -> OrgView:
    return await org.rename_org(conn, caller, body.name)


@router.get("/org/members", operation_id="listMembers")
async def list_members(caller: Caller, conn: Conn) -> list[Member]:
    return await members.list_members(conn, caller)


@router.delete("/org/members/{user_id}", operation_id="removeMember", status_code=204)
async def remove_member(user_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    """Remove a member (never the admin): they keep their account, in a new Free org of their own."""
    await members.remove_member(conn, caller, user_id)
    return Response(status_code=204)


@router.get("/org/invites", operation_id="listInvites")
async def list_invites(caller: Caller, conn: Conn) -> list[InviteView]:
    return await invites.list_invites(conn, caller)


@router.post("/org/invites", operation_id="createInvite", status_code=201)
async def create_invite(body: NewInvite, request: Request, caller: Caller, conn: Conn) -> CreatedInvite:
    """Invite by email: members are unlimited on every plan."""
    view, token = await invites.create_invite(conn, caller, body.email)
    return CreatedInvite(invite=view, link=f"{request.app.state.settings.invite_base}?invite={token}")


@router.delete("/org/invites/{invite_id}", operation_id="revokeInvite", status_code=204)
async def revoke_invite(invite_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    await invites.revoke_invite(conn, caller, invite_id)
    return Response(status_code=204)


@router.post("/invites/accept", operation_id="acceptInvite")
async def accept_invite(body: AcceptInvite, caller: Caller, conn: Conn) -> Joined:
    """Join the org that invited you: only when your own org has no one else and nothing paid; it is then removed."""
    return await joining.accept_invite(conn, caller, body.token)


@router.get("/org/sso", operation_id="getSso")
async def get_sso(request: Request, caller: Caller, conn: Conn) -> SsoView | None:
    """The org's single sign-on (OpenID Connect), or null; the client secret is never shown."""
    return await sso.get_sso(conn, caller, request.app.state.settings)


@router.put("/org/sso", operation_id="setSso")
async def set_sso(body: SsoIn, request: Request, caller: Caller, conn: Conn) -> SsoView:
    """Set or change the org's single sign-on: the admin's, on Enterprise (E_NOT_IN_PLAN `sso` elsewhere). The
    issuer's OpenID configuration is read first (E_UNAVAILABLE `discovery` when it cannot be); the client secret may
    be left out to keep the one set; a domain that is another org's is E_CONFLICT."""
    state = request.app.state
    return await sso.set_sso(conn, caller, state.settings, state.http, body)


@router.delete("/org/sso", operation_id="removeSso", status_code=204)
async def remove_sso(caller: Caller, conn: Conn) -> Response:
    """Single sign-on off: the org's people sign in with Google or GitHub again."""
    await sso.remove_sso(conn, caller)
    return Response(status_code=204)
