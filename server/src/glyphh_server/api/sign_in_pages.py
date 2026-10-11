"""Signing a member in: choose Google or GitHub, sign in there, then allow an agent host, or join an org.
Every step carries its purpose in a signed value and is tied to the browser that started it by a
short-lived cookie, so nobody can push their own sign-in into someone else's browser."""

import uuid

from fastapi import APIRouter, Form, Query, Request
from starlette.responses import RedirectResponse, Response

from glyphh_server.api.auth import Conn
from glyphh_server.api.browser_session import COOKIE, START_AGAIN, TTL, browser, callback_url, cfg, start_browser
from glyphh_server.api.join_pages import finish_join
from glyphh_server.errors import Forbidden, Invalid
from glyphh_server.ops import invites
from glyphh_server.ops.auth import codes, hosts, signed
from glyphh_server.ops.auth.providers import available, provider
from glyphh_server.ops.auth.signin import sign_in
from glyphh_server.pages import views

router = APIRouter(prefix="/auth", include_in_schema=False)


@router.get("/sign-in")
async def sign_in_page(request: Request, token: str = Query(alias="request")) -> Response:
    codes.read_pending(cfg(request).secret_key, token)
    return start_browser(views.sign_in(token, available(cfg(request))), cfg(request))


@router.get("/{name}/start")
async def start(
    name: str, request: Request, conn: Conn, token: str | None = Query(None, alias="request"), invite: str | None = None
) -> Response:
    settings = cfg(request)
    chosen = provider(name, settings)
    if invite:
        await invites.read_invite(conn, invite)
        purpose = {"i": invite}
    else:
        codes.read_pending(settings.secret_key, token or "")
        purpose = {"r": token}
    state = signed.sign(settings.secret_key, {**purpose, "p": name, "n": browser(request)}, TTL)
    return RedirectResponse(chosen.authorize_url(settings, callback_url(settings, name), state), status_code=302)


@router.get("/{name}/callback")
async def callback(name: str, request: Request, conn: Conn, state: str, code: str | None = None) -> Response:
    settings = cfg(request)
    chosen = provider(name, settings)
    st = signed.verify(settings.secret_key, state)
    if st["p"] != name or st["n"] != browser(request):
        raise Invalid(START_AGAIN)
    if not code:
        raise Forbidden("Signing in was cancelled. Start again from your app when you're ready.")
    if "i" in st:
        return await finish_join(request, conn, chosen, st["i"], code)
    pending = codes.read_pending(settings.secret_key, st["r"])
    profile = await chosen.profile(request.app.state.http, settings, code, callback_url(settings, name))
    user_id = await sign_in(conn, profile)
    host = await hosts.find(conn, pending.client_id)
    if host is None:
        raise Invalid("This app is not registered with Glyphh. Start again from your app.")
    consent = signed.sign(settings.secret_key, {"r": st["r"], "u": str(user_id), "n": st["n"]}, TTL)
    return views.allow(host.name, profile.email, consent)


@router.post("/allow")
async def allow(request: Request, conn: Conn, consent: str = Form(), decision: str = Form()) -> Response:
    c = signed.verify(cfg(request).secret_key, consent)
    if c["n"] != browser(request):
        raise Invalid(START_AGAIN)
    pending = codes.read_pending(cfg(request).secret_key, c["r"])
    if decision == "allow":
        back = await codes.approve(conn, pending, uuid.UUID(c["u"]))
    else:
        back = await codes.denied(conn, pending)
    res = RedirectResponse(back, status_code=303)
    res.delete_cookie(COOKIE, path="/auth")
    return res
