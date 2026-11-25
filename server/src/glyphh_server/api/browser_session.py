"""What every step of the device sign-in page shares: the provider callback address, and the short-lived cookie that
ties each step to the browser that started it, so nobody can push their sign-in into someone else's browser."""

from typing import Literal
from urllib.parse import urlsplit

from starlette.requests import Request
from starlette.responses import Response

from glyphh_server.config import Settings
from glyphh_server.errors import Invalid
from glyphh_server.ops.auth.secrets import make_secret

COOKIE: str = "glyphh_signin"
PATH: str = "/auth"  # the cookie's: every step of a sign-in is under it
TTL: int = 600
START_AGAIN: str = "This sign-in has expired or moved to another browser. Start again in Claude."


def cfg(request: Request) -> Settings:
    return request.app.state.settings


def callback_url(settings: Settings, provider: str) -> str:
    return f"{settings.base_url}/auth/{provider}/callback"


def browser(request: Request) -> str:
    found = request.cookies.get(COOKIE)
    if not found:
        raise Invalid(START_AGAIN)
    return found


def _site(url: str) -> str:
    """A URL's site, as SameSite sees it: its host's last two labels (glyphh.ai for api.glyphh.ai)."""
    return ".".join((urlsplit(url).hostname or "").split(".")[-2:])


def same_site(settings: Settings) -> Literal["lax", "none"]:
    """Lax when the platform and the server share a site. When they do not (locally, localhost beside a tunnel), the
    platform's read of /auth/consent is cross-site, so the cookie must be None, which browsers only keep when Secure."""
    if settings.public_url.startswith("https://") and _site(settings.public_url) != _site(settings.platform_url):
        return "none"
    return "lax"


def new_browser() -> str:
    """A fresh value for this browser, sent with the step that leaves for Google or GitHub."""
    return make_secret()


def bind_browser(response: Response, settings: Settings, value: str) -> Response:
    response.set_cookie(
        COOKIE,
        value,
        max_age=TTL,
        httponly=True,
        samesite=same_site(settings),
        path=PATH,
        secure=settings.public_url.startswith("https://"),
    )
    return response


def forget_browser(response: Response) -> Response:
    response.delete_cookie(COOKIE, path=PATH)
    return response
