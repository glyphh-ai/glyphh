"""The server renders nothing: whenever a browser is in a flow (the device sign-in, the connector's Allow, a provider
link, Stripe's return), it is sent to the platform, which shows the page and calls back here. Every
value in a redirect's query is URL-encoded; the platform's routes are listed in `glyphh-ai/platform`'s README."""

from urllib.parse import urlencode

from starlette.responses import RedirectResponse

from glyphh_server.config import Settings


def to_platform(settings: Settings, path: str, **params: str | None) -> RedirectResponse:
    """The browser on to the platform's page, with these query values (a None is left out)."""
    query = urlencode({k: v for k, v in params.items() if v is not None})
    return RedirectResponse(f"{settings.platform_base}{path}" + (f"?{query}" if query else ""), status_code=302)
