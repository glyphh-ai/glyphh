"""Signing a member in for an agent host: choose Google or GitHub, sign in there, allow the host.
Every step carries the host's request in a signed value and is tied to the browser that started it
by a short-lived cookie, so nobody can push their own sign-in into someone else's browser."""

import uuid

from fastapi import APIRouter, Form, Query, Request
from starlette.responses import RedirectResponse, Response

from glyphh_server.api.auth import Conn
from glyphh_server.config import Settings
from glyphh_server.errors import Forbidden, Invalid
from glyphh_server.ops.auth import codes, hosts, signed
from glyphh_server.ops.auth.providers import available, provider
from glyphh_server.ops.auth.secrets import make_secret
from glyphh_server.ops.auth.signin import sign_in
from glyphh_server.pages import views

router = APIRouter(prefix="/auth", include_in_schema=False)
COOKIE: str = "glyphh_signin"
TTL: int = 600
START_AGAIN: str = "This sign-in has expired or moved to another browser. Start again from your app."


def _cfg(request: Request) -> Settings:
    return request.app.state.settings


def _callback(cfg: Settings, name: str) -> str:
    return f"{cfg.public_url.rstrip('/')}/auth/{name}/callback"


def _browser(request: Request) -> str:
    found = request.cookies.get(COOKIE)
    if not found:
        raise Invalid(START_AGAIN)
    return found


@router.get("/sign-in")
async def sign_in_page(request: Request, token: str = Query(alias="request")) -> Response:
    cfg = _cfg(request)
    codes.read_pending(cfg.secret_key, token)
    res = views.sign_in(token, available(cfg))
    res.set_cookie(
        COOKIE,
        make_secret(),
        max_age=TTL,
        httponly=True,
        samesite="lax",
        path="/auth",
        secure=cfg.public_url.startswith("https://"),
    )
    return res


@router.get("/{name}/start")
async def start(name: str, request: Request, token: str = Query(alias="request")) -> Response:
    cfg = _cfg(request)
    chosen = provider(name, cfg)
    codes.read_pending(cfg.secret_key, token)
    state = signed.sign(cfg.secret_key, {"r": token, "p": name, "n": _browser(request)}, TTL)
    return RedirectResponse(chosen.authorize_url(cfg, _callback(cfg, name), state), status_code=302)


@router.get("/{name}/callback")
async def callback(name: str, request: Request, conn: Conn, state: str, code: str | None = None) -> Response:
    cfg = _cfg(request)
    chosen = provider(name, cfg)
    st = signed.verify(cfg.secret_key, state)
    if st["p"] != name or st["n"] != _browser(request):
        raise Invalid(START_AGAIN)
    if not code:
        raise Forbidden("Signing in was cancelled. Start again from your app when you're ready.")
    pending = codes.read_pending(cfg.secret_key, st["r"])
    profile = await chosen.profile(request.app.state.http, cfg, code, _callback(cfg, name))
    user_id = await sign_in(conn, profile)
    host = await hosts.find(conn, pending.client_id)
    if host is None:
        raise Invalid("This app is not registered with Glyphh. Start again from your app.")
    consent = signed.sign(cfg.secret_key, {"r": st["r"], "u": str(user_id), "n": st["n"]}, TTL)
    return views.allow(host.name, profile.email, consent)


@router.post("/allow")
async def allow(request: Request, conn: Conn, consent: str = Form(), decision: str = Form()) -> Response:
    cfg = _cfg(request)
    c = signed.verify(cfg.secret_key, consent)
    if c["n"] != _browser(request):
        raise Invalid(START_AGAIN)
    pending = codes.read_pending(cfg.secret_key, c["r"])
    if decision == "allow":
        back = await codes.approve(conn, pending, uuid.UUID(c["u"]))
    else:
        back = await codes.denied(conn, pending)
    res = RedirectResponse(back, status_code=303)
    res.delete_cookie(COOKIE, path="/auth")
    return res
