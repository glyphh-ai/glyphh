"""The platform's sign-in, for a browser. Nothing is rendered: a good authorization request sends the browser to the
platform's `/authorize` page (sign in with a provider, api/signin_pages.py, tied to the browser by a cookie), and the
provider's callback sends it to the platform's `/allow` page, which reads `GET /auth/consent` and answers with
`GET /auth/oauth/allow`. Allow or Deny goes back to the client's redirect URI with the state and the issuer
(RFC 9207)."""

import uuid
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse, Response

from glyphh_server.api.auth import Conn
from glyphh_server.api.browser_session import START_AGAIN, TTL, browser, callback_url, cfg, forget_browser
from glyphh_server.api.gone import staff_only
from glyphh_server.api.pages import to_platform
from glyphh_server.config import Settings
from glyphh_server.errors import Invalid
from glyphh_server.ops.auth import signed
from glyphh_server.ops.auth.providers import Provider
from glyphh_server.ops.auth.signin import sign_in
from glyphh_server.ops.connector import authorize, codes
from glyphh_server.ops.connector.authorize import AuthorizeRequest
from glyphh_server.ops.connector.errors import AuthorizeRefused

router = APIRouter()
OAUTH: str = "oauth"
ALLOW: str = "oauth-allow"


def back_to(uri: str, settings: Settings, **params: str | None) -> RedirectResponse:
    """The client's redirect URI with these parameters added to its own query, and the issuer."""
    parts = urlsplit(uri)
    added = urlencode({k: v for k, v in {**params, "iss": settings.base_url}.items() if v is not None})
    query = f"{parts.query}&{added}" if parts.query else added
    return RedirectResponse(urlunsplit(parts._replace(query=query)), status_code=302)


@router.get("/oauth/authorize", operation_id="oauthAuthorize", tags=["sign-in"], response_class=RedirectResponse)
async def authorize_page(request: Request, conn: Conn) -> Response:
    """The authorization request (OAuth 2.1, PKCE S256). An unknown client or redirect URI is E_INVALID here, never
    a redirect; any other refusal goes back to the client; a good request goes on to the platform's `/authorize`
    page with the request signed (`oauth`) and the client's name."""
    settings, q = cfg(request), dict(request.query_params)
    try:
        req = await authorize.check(conn, settings, q)
    except AuthorizeRefused as err:
        refused = {"error": err.error, "error_description": err.description, "state": q.get("state")}
        return back_to(q["redirect_uri"], settings, **refused)
    value = signed.sign(settings.secret_key, {"k": OAUTH, "q": req.signed()}, TTL)
    return to_platform(settings, "/authorize", oauth=value, client=req.client_name)


def purpose(settings: Settings, provider: str, value: str) -> dict[str, Any]:
    """What the authorization page's signed value asks for: sign in with this provider for this request."""
    found = signed.verify(settings.secret_key, value)
    if found.get("k") != OAUTH:
        raise Invalid(START_AGAIN)
    return {"k": OAUTH, "q": found["q"], "p": provider}


def is_oauth(state: dict[str, Any]) -> bool:
    return state.get("k") == OAUTH


async def allow_page(request: Request, conn: Conn, chosen: Provider, state: dict[str, Any], code: str) -> Response:
    """Back from the provider: the person is signed in; on to the platform's `/allow` page with the consent signed
    and tied to this browser."""
    settings = cfg(request)
    profile = await chosen.profile(request.app.state.http, settings, code, callback_url(settings, state["p"]))
    staff_only(settings, profile.email)  # nobody else signs in, and nobody signs up
    user_id = await sign_in(conn, profile)
    consent = {"k": ALLOW, "q": state["q"], "u": str(user_id), "n": state["n"], "e": profile.email.lower()}
    return to_platform(settings, "/allow", consent=signed.sign(settings.secret_key, consent, TTL))


def about(consent: dict[str, Any]) -> dict[str, Any]:
    """What the Allow page shows: the client, where it returns to, who is signed in."""
    req = AuthorizeRequest(**consent["q"])
    return {
        "client": req.client_name,
        "returns_to": urlsplit(req.redirect_uri).hostname,
        "resource": req.resource,
        "email": consent["e"],
    }


@router.get("/auth/oauth/allow", include_in_schema=False)
async def allow(request: Request, conn: Conn, consent: str, decision: str) -> Response:
    """The person's answer from the platform's Allow page: a code back to the client, or access_denied."""
    settings = cfg(request)
    c = signed.verify(settings.secret_key, consent)
    if c.get("k") != ALLOW or c["n"] != browser(request):
        raise Invalid(START_AGAIN)
    req = AuthorizeRequest(**c["q"])
    if decision != "allow":
        return forget_browser(back_to(req.redirect_uri, settings, error="access_denied", state=req.state))
    code = await codes.issue(conn, req, uuid.UUID(c["u"]))
    return forget_browser(back_to(req.redirect_uri, settings, code=code, state=req.state))
