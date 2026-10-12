"""What the platform's sign-in screens show, read with the step's own signed value; nothing here signs anyone
in. Each answer is only what the screen needs, and a forged or expired value is refused."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from glyphh_server.api.auth import Conn
from glyphh_server.api.browser_session import cfg
from glyphh_server.ops import invites
from glyphh_server.ops.auth import codes, signed
from glyphh_server.ops.auth.providers import available
from glyphh_server.ops.me import MeOrg, my_orgs

router = APIRouter(prefix="/v1/auth", tags=["sign-in"])


class SignInScreen(BaseModel):
    providers: list[str]


class AllowScreen(BaseModel):
    host: str
    email: str
    orgs: list[MeOrg]


class JoinScreen(BaseModel):
    org: str
    email: str
    role: Literal["org_admin", "user"]
    invited_by: str | None
    expires_at: datetime
    providers: list[str]


@router.get("/sign-in", operation_id="signInScreen")
async def sign_in_screen(request: Request, request_token: str = Query(alias="request")) -> SignInScreen:
    codes.read_pending(cfg(request).secret_key, request_token)
    return SignInScreen(providers=available(cfg(request)))


@router.get("/allow", operation_id="allowScreen")
async def allow_screen(request: Request, conn: Conn, consent: str) -> AllowScreen:
    c = signed.verify(cfg(request).secret_key, consent)
    return AllowScreen(host=c["h"], email=c["e"], orgs=await my_orgs(conn, uuid.UUID(c["u"])))


@router.get("/join", operation_id="joinScreen")
async def join_screen(request: Request, conn: Conn, invite: str) -> JoinScreen:
    found = await invites.read_invite(conn, invite)
    return JoinScreen(
        org=found.org,
        email=found.email,
        role=found.role,
        invited_by=found.invited_by,
        expires_at=found.expires_at,
        providers=available(cfg(request)),
    )
