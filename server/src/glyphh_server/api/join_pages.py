"""Joining an org from an invite: back from Google or GitHub, accept as that email, and you're in."""

from starlette.requests import Request
from starlette.responses import Response

from glyphh_server.api.auth import Conn
from glyphh_server.api.browser_session import COOKIE, callback_url, cfg, screen
from glyphh_server.ops import invites
from glyphh_server.ops.auth.providers import Provider
from glyphh_server.ops.auth.signin import sign_in


async def finish_join(request: Request, conn: Conn, chosen: Provider, invite: str, code: str) -> Response:
    """Sign in (which makes the person, with their Personal org, the first time), then accept as their email."""
    settings = cfg(request)
    profile = await chosen.profile(request.app.state.http, settings, code, callback_url(settings, chosen.NAME))
    user_id = await sign_in(conn, profile)
    org = await invites.accept_invite(conn, invite, user_id)
    res = screen(settings, "/joined", org=org)
    res.delete_cookie(COOKIE, path="/auth")
    return res
