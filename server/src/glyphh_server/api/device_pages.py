"""The device sign-in and the shared provider steps, for a browser. Nothing is rendered: the browser is sent to the
platform's pages, each step after the first carrying its purpose in a signed value tied to the browser that started
it by a short-lived cookie.

The device flow: the link opens `GET /v1/device?code=` → the platform's `/device` page (the code, Continue with a
provider) → `GET /auth/{provider}/start?code=` → the provider → `GET /auth/{provider}/callback` → the platform's
`/device/approve?consent=` page, which reads `GET /auth/consent` and answers with `GET /auth/approve`."""

import uuid
from typing import Any

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse, Response

from glyphh_server.api import link_pages, oauth_pages
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
from glyphh_server.api.pages import to_platform
from glyphh_server.errors import Forbidden, Invalid
from glyphh_server.ops import device_approval
from glyphh_server.ops.auth import signed
from glyphh_server.ops.auth.providers import available, provider
from glyphh_server.ops.auth.signin import sign_in

router = APIRouter()
DEVICE: str = "device"


@router.get("/v1/device", operation_id="deviceSignInPage", tags=["device flow"], response_class=RedirectResponse)
async def device_page(request: Request, conn: Conn, code: str | None = None) -> Response:
    """The sign-in link, opened in a browser: on to the platform's `/device` page with the code (checked here: an
    expired or unknown one is E_INVALID), or without one for the person to type it."""
    if not code:
        return to_platform(cfg(request), "/device")
    found = await device_approval.waiting(conn, code)
    return to_platform(cfg(request), "/device", code=found.user_code)


@router.get("/auth/providers", operation_id="signInProviders", tags=["device flow"])
async def providers(request: Request) -> dict[str, list[str]]:
    """The sign-in providers this server offers (google, github), for the platform's Continue buttons."""
    return {"providers": list(available(cfg(request)))}


@router.get("/auth/{name}/start", include_in_schema=False)
async def start(
    name: str,
    request: Request,
    conn: Conn,
    code: str | None = None,
    link: str | None = None,
    oauth: str | None = None,
) -> Response:
    """Off to the provider, for a device sign-in (`code`), to link the provider to an account (`link`), or to allow
    the connector (`oauth`)."""
    settings = cfg(request)
    chosen = provider(name, settings)
    if oauth:
        purpose = oauth_pages.purpose(settings, name, oauth)
    elif link:
        purpose = link_pages.purpose(settings, name, link)
    elif code:
        purpose = {"c": (await device_approval.waiting(conn, code)).user_code, "p": name}
    else:
        raise Invalid(START_AGAIN)
    nonce = new_browser()
    state = signed.sign(settings.secret_key, {**purpose, "n": nonce}, TTL)
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
    if link_pages.is_link(st):
        return await link_pages.finish(request, conn, chosen, st, code)
    if oauth_pages.is_oauth(st):
        return await oauth_pages.allow_page(request, conn, chosen, st, code)
    found = await device_approval.waiting(conn, st["c"])
    profile = await chosen.profile(request.app.state.http, settings, code, callback_url(settings, name))
    user_id = await sign_in(conn, profile)
    about = {"name": found.name, "surface": found.surface, "email": profile.email.lower()}
    consent = {"k": DEVICE, "c": found.user_code, "u": str(user_id), "n": st["n"], "d": about}
    return to_platform(settings, "/device/approve", consent=signed.sign(settings.secret_key, consent, TTL))


def consent_of(request: Request, consent: str) -> dict[str, Any]:
    """A signed consent, checked and tied to this browser."""
    c = signed.verify(cfg(request).secret_key, consent)
    if c.get("k") not in (DEVICE, oauth_pages.ALLOW) or c.get("n") != browser(request):
        raise Invalid(START_AGAIN)
    return c


@router.get("/auth/consent", include_in_schema=False)
async def consent_view(request: Request, consent: str) -> dict[str, Any]:
    """What a consent asks, for the platform's page: a device sign-in (the install's name and surface, the code,
    the email signed in) or the connector's Allow (the client, where it returns to, the email)."""
    c = consent_of(request, consent)
    if c["k"] == DEVICE:
        return {"kind": "device", "code": c["c"], **c["d"]}
    return {"kind": "oauth", **oauth_pages.about(c)}


@router.get("/auth/approve", include_in_schema=False)
async def approve(request: Request, conn: Conn, consent: str, decision: str) -> Response:
    """The person's answer to a device sign-in, from the platform's page: approve or deny, then on to the platform's
    `/device/done`. A consent used again is refused (its code is no longer waiting)."""
    c = consent_of(request, consent)
    if c["k"] != DEVICE:
        raise Invalid(START_AGAIN)
    if decision == "approve":
        await device_approval.approve(conn, c["c"], uuid.UUID(c["u"]))
    else:
        await device_approval.deny(conn, c["c"])
    done = to_platform(cfg(request), "/device/done", result="approved" if decision == "approve" else "denied")
    return forget_browser(done)
