"""The page the device flow's link opens: the code, Continue with Google or GitHub, then approve or deny this
install. Each step after the first carries its purpose in a signed value and is tied to the browser that started it
by a short-lived cookie."""

import uuid
from html import escape
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from starlette.responses import RedirectResponse, Response

from glyphh_server.api.auth import Conn
from glyphh_server.api.browser_session import (
    START_AGAIN,
    TTL,
    bind_browser,
    browser,
    callback_url,
    cfg,
    forget_browser,
    new_browser,
)
from glyphh_server.api.pages import link, page
from glyphh_server.errors import Forbidden, Invalid
from glyphh_server.ops import device_approval
from glyphh_server.ops.auth import signed
from glyphh_server.ops.auth.providers import available, provider
from glyphh_server.ops.auth.signin import sign_in

router = APIRouter()
ASK_CODE: str = (
    '<form method="get" action="/v1/device"><label>Code <input name="code" autocomplete="off"></label>'
    ' <button type="submit">Continue</button></form>'
)
NAMES: dict[str, str] = {"google": "Google", "github": "GitHub"}


@router.get("/v1/device", operation_id="deviceSignInPage", tags=["device flow"], response_class=HTMLResponse)
async def device_page(request: Request, conn: Conn, code: str | None = None) -> Response:
    """The page the sign-in link opens, in a browser: Continue with Google or GitHub, then approve this install."""
    if not code:
        return page("Sign in to Glyphh", "Enter the code Claude shows you.", raw=ASK_CODE)
    found = await device_approval.waiting(conn, code)
    query = urlencode({"code": found.user_code})
    choices = [link(f"/auth/{p}/start?{query}", f"Continue with {NAMES[p]}") for p in available(cfg(request))]
    return page(
        "Sign in to Glyphh",
        f"Code {found.user_code}: check it matches the one Claude shows.",
        *([] if choices else ["No sign-in provider is set up on this server."]),
        raw="".join(choices),
    )


@router.get("/auth/{name}/start", include_in_schema=False)
async def start(name: str, request: Request, conn: Conn, code: str) -> Response:
    settings = cfg(request)
    chosen = provider(name, settings)
    found = await device_approval.waiting(conn, code)
    nonce = new_browser()
    state = signed.sign(settings.secret_key, {"c": found.user_code, "p": name, "n": nonce}, TTL)
    away = RedirectResponse(chosen.authorize_url(settings, callback_url(settings, name), state), status_code=302)
    return bind_browser(away, settings, nonce)


@router.get("/auth/{name}/callback", include_in_schema=False)
async def callback(name: str, request: Request, conn: Conn, state: str, code: str | None = None) -> Response:
    settings = cfg(request)
    chosen = provider(name, settings)
    st = signed.verify(settings.secret_key, state)
    if st["p"] != name or st["n"] != browser(request):
        raise Invalid(START_AGAIN)
    if not code:
        raise Forbidden("Signing in was cancelled. Start again in Claude when you're ready.", reason="cancelled")
    found = await device_approval.waiting(conn, st["c"])
    profile = await chosen.profile(request.app.state.http, settings, code, callback_url(settings, name))
    user_id = await sign_in(conn, profile)
    consent = signed.sign(settings.secret_key, {"c": found.user_code, "u": str(user_id), "n": st["n"]}, TTL)
    form = (
        f'<form method="post" action="/auth/approve"><input type="hidden" name="consent" value="{escape(consent)}">'
        '<button type="submit" name="decision" value="approve">Approve</button> '
        '<button type="submit" name="decision" value="deny">Deny</button></form>'
    )
    return page(
        "Approve this sign-in",
        f"{found.name} ({found.surface}) wants to sign in to Glyphh as {profile.email.lower()}.",
        f"Code {found.user_code}.",
        raw=form,
    )


@router.post("/auth/approve", include_in_schema=False)
async def approve(
    request: Request, conn: Conn, consent: Annotated[str, Form()], decision: Annotated[str, Form()]
) -> Response:
    c = signed.verify(cfg(request).secret_key, consent)
    if c["n"] != browser(request):
        raise Invalid(START_AGAIN)
    if decision == "approve":
        await device_approval.approve(conn, c["c"], uuid.UUID(c["u"]))
        done = page("Signed in", "Signed in. Go back to Claude.")
    else:
        await device_approval.deny(conn, c["c"])
        done = page("Sign-in denied", "Nothing was signed in. You can close this page.")
    return forget_browser(done)
