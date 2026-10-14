"""What every step of the device sign-in page shares: the provider callback address, and the short-lived cookie that
ties each step to the browser that started it, so nobody can push their sign-in into someone else's browser. Installing
the GitHub App is tied to its browser by the same cookie, on its own path."""

from starlette.requests import Request
from starlette.responses import Response

from glyphh_server.config import Settings
from glyphh_server.errors import Invalid
from glyphh_server.ops.auth.secrets import make_secret

COOKIE: str = "glyphh_signin"
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


def new_browser() -> str:
    """A fresh value for this browser, sent with the step that leaves for Google or GitHub."""
    return make_secret()


def bind_browser(response: Response, settings: Settings, value: str, path: str = "/auth") -> Response:
    response.set_cookie(
        COOKIE,
        value,
        max_age=TTL,
        httponly=True,
        samesite="lax",
        path=path,
        secure=settings.public_url.startswith("https://"),
    )
    return response


def forget_browser(response: Response, path: str = "/auth") -> Response:
    response.delete_cookie(COOKIE, path=path)
    return response
