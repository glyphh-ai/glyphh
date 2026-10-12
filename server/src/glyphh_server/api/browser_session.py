"""What every sign-in step shares: the settings, the provider callback address, the short-lived cookie that
ties each step to the browser that started it, and the way to a platform screen."""

from urllib.parse import urlencode

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from glyphh_server.config import Settings
from glyphh_server.errors import Invalid
from glyphh_server.ops.auth.secrets import make_secret

COOKIE: str = "glyphh_signin"
TTL: int = 600
START_AGAIN: str = "This sign-in has expired or moved to another browser. Start again from your app."


def cfg(request: Request) -> Settings:
    return request.app.state.settings


def callback_url(settings: Settings, provider: str) -> str:
    return f"{settings.public_url.rstrip('/')}/auth/{provider}/callback"


def browser(request: Request) -> str:
    found = request.cookies.get(COOKIE)
    if not found:
        raise Invalid(START_AGAIN)
    return found


def new_browser() -> str:
    """A fresh value for this browser, sent with the step that leaves for Google or GitHub."""
    return make_secret()


def bind_browser(response: Response, settings: Settings, value: str) -> Response:
    response.set_cookie(
        COOKIE,
        value,
        max_age=TTL,
        httponly=True,
        samesite="lax",
        path="/auth",
        secure=settings.public_url.startswith("https://"),
    )
    return response


def screen(settings: Settings, path: str, **query: str) -> RedirectResponse:
    """Send the browser to one of the platform's sign-in screens."""
    return RedirectResponse(f"{settings.platform}{path}?{urlencode(query)}", status_code=303)
