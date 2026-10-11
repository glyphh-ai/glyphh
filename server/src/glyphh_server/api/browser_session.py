"""What every sign-in page shares: the settings, the provider callback address, and the short-lived
cookie that ties each step to the browser that started it."""

from starlette.requests import Request
from starlette.responses import Response

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


def start_browser(response: Response, settings: Settings) -> Response:
    response.set_cookie(
        COOKIE,
        make_secret(),
        max_age=TTL,
        httponly=True,
        samesite="lax",
        path="/auth",
        secure=settings.public_url.startswith("https://"),
    )
    return response
