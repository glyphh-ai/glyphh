"""The platform's session: a code becomes tokens, the refresh token rides an httpOnly cookie the page can't read,
and the short access token is the page's, in memory. Refresh, switch org and sign out all go through here."""

import uuid

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.config import Settings
from glyphh_server.errors import Unauthorized
from glyphh_server.ops.auth import platform, tokens
from glyphh_server.ops.auth.tokens import REFRESH_TTL, IssuedTokens

router = APIRouter(prefix="/v1/session", tags=["session"])
COOKIE: str = "glyphh_session"


class CodeIn(BaseModel):
    code: str
    verifier: str


class OrgIn(BaseModel):
    org: uuid.UUID


class Access(BaseModel):
    access_token: str
    expires_in: int


def _answer(request: Request, response: Response, issued: IssuedTokens) -> Access:
    settings: Settings = request.app.state.settings
    response.set_cookie(
        COOKIE,
        issued.refresh_token,
        max_age=int(REFRESH_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        path="/v1/session",
        secure=settings.public_url.startswith("https://"),
    )
    return Access(access_token=issued.access_token, expires_in=issued.expires_in)


def _refresh(request: Request) -> str:
    found = request.cookies.get(COOKIE)
    if not found:
        raise Unauthorized("Sign in to Glyphh.", reason="signed_out")
    return found


@router.post("/token", operation_id="startSession")
async def start(body: CodeIn, request: Request, response: Response, conn: Conn) -> Access:
    return _answer(request, response, await platform.exchange(conn, body.code, body.verifier))


@router.post("/refresh", operation_id="refreshSession")
async def refresh(request: Request, response: Response, conn: Conn) -> Access:
    return _answer(request, response, await tokens.rotate(conn, _refresh(request)))


@router.post("/switch", operation_id="switchOrg")
async def switch(body: OrgIn, caller: Caller, request: Request, response: Response, conn: Conn) -> Access:
    if (old := request.cookies.get(COOKIE)) is not None:
        await tokens.revoke(conn, old)
    return _answer(request, response, await platform.switch(conn, caller, body.org))


@router.post("/sign-out", operation_id="signOut", status_code=204)
async def sign_out(request: Request, conn: Conn) -> Response:
    if (old := request.cookies.get(COOKIE)) is not None:
        await tokens.revoke(conn, old)
    gone = Response(status_code=204)
    gone.delete_cookie(COOKIE, path="/v1/session")
    return gone
