"""The provider steps of the platform's sign-in, for a browser. Nothing is rendered: the browser is sent on, each
step after the first carrying its purpose in a signed value tied to the browser that started it by a short-lived
cookie.

The platform's `/authorize` page (reached from `GET /oauth/authorize`, api/oauth_pages.py) offers the providers
(`GET /auth/providers`) → `GET /auth/{provider}/start?oauth=` → Google or GitHub → `GET /auth/{provider}/callback` →
the platform's `/allow?consent=` page, which reads `GET /auth/consent` and answers with `GET /auth/oauth/allow`."""

from typing import Any

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse, Response

from glyphh_server.api import oauth_pages
from glyphh_server.api.auth import Conn
from glyphh_server.api.browser_session import START_AGAIN, TTL, bind_browser, browser, callback_url, cfg, new_browser
from glyphh_server.errors import Forbidden, Invalid
from glyphh_server.ops.auth import signed
from glyphh_server.ops.auth.providers import available, provider

router = APIRouter()


@router.get("/auth/providers", operation_id="signInProviders", tags=["sign-in"])
async def providers(request: Request) -> dict[str, Any]:
    """The sign-in providers this server offers (google, github), for the platform's Continue buttons. `sso` is
    always false: single sign-on went with the products, and the platform's page still reads the key."""
    return {"providers": list(available(cfg(request))), "sso": False}


@router.get("/auth/{name}/start", include_in_schema=False)
async def start(name: str, request: Request, oauth: str | None = None) -> Response:
    """Off to the provider, for the authorization request the signed `oauth` value carries."""
    settings = cfg(request)
    chosen = provider(name, settings)
    if not oauth:
        raise Invalid(START_AGAIN)
    nonce = new_browser()
    state = signed.sign(settings.secret_key, {**oauth_pages.purpose(settings, name, oauth), "n": nonce}, TTL)
    away = RedirectResponse(chosen.authorize_url(settings, callback_url(settings, name), state), status_code=302)
    return bind_browser(away, settings, nonce)


@router.get("/auth/{name}/callback", include_in_schema=False)
async def callback(name: str, request: Request, conn: Conn, state: str, code: str | None = None) -> Response:
    settings = cfg(request)
    st = signed.verify(settings.secret_key, state)
    if st.get("p") != name or st.get("n") != browser(request) or not oauth_pages.is_oauth(st):
        raise Invalid(START_AGAIN)
    chosen = provider(name, settings)
    if not code:
        raise Forbidden("Signing in was cancelled. Start again when you're ready.", reason="cancelled")
    return await oauth_pages.allow_page(request, conn, chosen, st, code)


@router.get("/auth/consent", include_in_schema=False)
async def consent_view(request: Request, consent: str) -> dict[str, Any]:
    """What a consent asks, for the platform's Allow page: the client, where it returns to, the email signed in."""
    c = signed.verify(cfg(request).secret_key, consent)
    if c.get("k") != oauth_pages.ALLOW or c.get("n") != browser(request):
        raise Invalid(START_AGAIN)
    return {"kind": "oauth", **oauth_pages.about(c)}
