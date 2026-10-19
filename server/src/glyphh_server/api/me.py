"""The signed-in person: who they are, the providers they sign in with, their installs, signing out."""

import uuid
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Cfg, Conn
from glyphh_server.api.link_pages import link_url
from glyphh_server.ops import identities, installs, me
from glyphh_server.ops.auth.providers import provider as configured
from glyphh_server.ops.installs import InstallView
from glyphh_server.ops.me import Me

router = APIRouter(prefix="/v1", tags=["account"])


ProviderName = Literal["google", "github"]


class Rename(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class LinkIn(BaseModel):
    provider: ProviderName


class LinkOut(BaseModel):
    url: str = Field(description="Open in a browser within 10 minutes: through the provider, then linked")


@router.get("/me", operation_id="me")
async def get_me(caller: Caller, conn: Conn, settings: Cfg) -> Me:
    """The user, their org and role, the plan version with its limits and features, the precedents its hosted runtimes
    hold and its hosting this month."""
    return await me.me(conn, caller, settings)


@router.patch("/me", operation_id="renameMe")
async def rename_me(body: Rename, caller: Caller, conn: Conn, settings: Cfg) -> Me:
    return await me.rename_me(conn, caller, body.name, settings)


@router.post("/me/identities", operation_id="linkIdentity")
async def link_identity(body: LinkIn, request: Request, caller: Caller, conn: Conn) -> LinkOut:
    """A link that adds Google or GitHub to this account, so either signs the person in."""
    settings = request.app.state.settings
    configured(body.provider, settings)
    await identities.can_link(conn, caller, body.provider)
    return LinkOut(url=link_url(settings, caller.user_id, body.provider))


@router.delete("/me/identities/{provider}", operation_id="unlinkIdentity", status_code=204)
async def unlink_identity(provider: ProviderName, caller: Caller, conn: Conn) -> Response:
    """Stop signing in with this provider; refused when it is the last one."""
    await identities.unlink(conn, caller, provider)
    return Response(status_code=204)


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
