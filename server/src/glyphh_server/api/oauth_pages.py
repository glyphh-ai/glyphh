"""The connector's pages, in a browser: the authorization request, signing in with Google or GitHub through the same
provider pages as the device sign-in (tied to the browser by the same cookie), then the Allow page. Allow or Deny goes
back to the client's redirect URI with the state and the issuer (RFC 9207)."""

import uuid
from html import escape
from typing import Annotated, Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from starlette.responses import RedirectResponse, Response

from glyphh_server.api.auth import Conn
from glyphh_server.api.browser_session import START_AGAIN, TTL, browser, callback_url, cfg, forget_browser
from glyphh_server.api.pages import link, page
from glyphh_server.config import Settings
from glyphh_server.errors import Invalid
from glyphh_server.ops.auth import signed
from glyphh_server.ops.auth.providers import Provider, available
from glyphh_server.ops.auth.signin import sign_in
from glyphh_server.ops.connector import authorize, codes
from glyphh_server.ops.connector.authorize import AuthorizeRequest
from glyphh_server.ops.connector.errors import AuthorizeRefused
from glyphh_server.ops.identities import NAMES

router = APIRouter()
OAUTH: str = "oauth"
ALLOW: str = "oauth-allow"


def back_to(uri: str, settings: Settings, **params: str | None) -> RedirectResponse:
    """The client's redirect URI with these parameters added to its own query, and the issuer."""
    parts = urlsplit(uri)
    added = urlencode({k: v for k, v in {**params, "iss": settings.base_url}.items() if v is not None})
    query = f"{parts.query}&{added}" if parts.query else added
    return RedirectResponse(urlunsplit(parts._replace(query=query)), status_code=302)


@router.get("/oauth/authorize", operation_id="oauthAuthorize", tags=["connector"], response_class=HTMLResponse)
async def authorize_page(request: Request, conn: Conn) -> Response:
    """The authorization request (OAuth 2.1, PKCE S256): sign in with Google or GitHub, then allow the client."""
    settings, q = cfg(request), dict(request.query_params)
    try:
        req = await authorize.check(conn, settings, q)
    except AuthorizeRefused as err:
        refused = {"error": err.error, "error_description": err.description, "state": q.get("state")}
        return back_to(q["redirect_uri"], settings, **refused)
    value = urlencode({OAUTH: signed.sign(settings.secret_key, {"k": OAUTH, "q": req.signed()}, TTL)})
    choices = [link(f"/auth/{p}/start?{value}", f"Continue with {NAMES[p]}") for p in available(settings)]
    return page(
        "Sign in to Glyphh",
        f"{req.client_name} wants to use your Glyphh account. Sign in to choose.",
        *([] if choices else ["No sign-in provider is set up on this server."]),
        raw="".join(choices),
    )


def purpose(settings: Settings, provider: str, value: str) -> dict[str, Any]:
    """What the authorization page's signed value asks for: sign in with this provider for this request."""
    found = signed.verify(settings.secret_key, value)
    if found.get("k") != OAUTH:
        raise Invalid(START_AGAIN)
    return {"k": OAUTH, "q": found["q"], "p": provider}


def is_oauth(state: dict[str, Any]) -> bool:
    return state.get("k") == OAUTH


async def allow_page(request: Request, conn: Conn, chosen: Provider, state: dict[str, Any], code: str) -> Response:
    """Back from the provider: the person is signed in; now Allow or Deny, the form signed and tied to this
    browser."""
    settings = cfg(request)
    req = AuthorizeRequest(**state["q"])
    profile = await chosen.profile(request.app.state.http, settings, code, callback_url(settings, state["p"]))
    user_id = await sign_in(conn, profile)
    consent = signed.sign(settings.secret_key, {"k": ALLOW, "q": state["q"], "u": str(user_id), "n": state["n"]}, TTL)
    form = (
        f'<form method="post" action="/auth/oauth/allow"><input type="hidden" name="consent" value="{escape(consent)}">'
        '<button type="submit" name="decision" value="allow">Allow</button> '
        '<button type="submit" name="decision" value="deny">Deny</button></form>'
    )
    return page(
        f"Allow {req.client_name} to use your Glyphh account?",
        f"Signed in as {profile.email.lower()}.",
        f"It will see your account, plan and billing, and can change them as you can. It returns to "
        f"{urlsplit(req.redirect_uri).hostname}.",
        raw=form,
    )


@router.post("/auth/oauth/allow", include_in_schema=False)
async def allow(
    request: Request, conn: Conn, consent: Annotated[str, Form()], decision: Annotated[str, Form()]
) -> Response:
    settings = cfg(request)
    c = signed.verify(settings.secret_key, consent)
    if c.get("k") != ALLOW or c["n"] != browser(request):
        raise Invalid(START_AGAIN)
    req = AuthorizeRequest(**c["q"])
    if decision != "allow":
        return forget_browser(back_to(req.redirect_uri, settings, error="access_denied", state=req.state))
    code = await codes.issue(conn, req, uuid.UUID(c["u"]))
    return forget_browser(back_to(req.redirect_uri, settings, code=code, state=req.state))
