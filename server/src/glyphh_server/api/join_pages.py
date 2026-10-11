"""Joining an org from an invite link: see what it is, sign in as the invited email, and you're in."""

from fastapi import APIRouter, Query, Request
from starlette.responses import Response

from glyphh_server.api.auth import Conn
from glyphh_server.api.browser_session import COOKIE, callback_url, cfg, start_browser
from glyphh_server.ops import invites
from glyphh_server.ops.auth.providers import Provider, available
from glyphh_server.ops.auth.signin import sign_in
from glyphh_server.pages import views

router = APIRouter(prefix="/auth", include_in_schema=False)


@router.get("/join")
async def join_page(request: Request, conn: Conn, invite: str = Query()) -> Response:
    found = await invites.read_invite(conn, invite)
    return start_browser(views.join(found.org, found.email, found.role, invite, available(cfg(request))), cfg(request))


async def finish_join(request: Request, conn: Conn, chosen: Provider, invite: str, code: str) -> Response:
    """Back from the provider: accept as that email, then sign in (which links the provider account)."""
    settings = cfg(request)
    profile = await chosen.profile(request.app.state.http, settings, code, callback_url(settings, chosen.NAME))
    org = await invites.accept_invite(conn, invite, profile.email, profile.first_name, profile.last_name)
    await sign_in(conn, profile)
    res = views.joined(org)
    res.delete_cookie(COOKIE, path="/auth")
    return res
