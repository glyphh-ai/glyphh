"""Installing the Glyphh GitHub App, in a browser. The link the API hands out carries a signed value naming the person;
opening it ties this browser to the install by a short-lived cookie and goes on to GitHub's install page, whose
answer comes back to the callback. The callback records the installation only for the browser that started it, and
only when GitHub says it is on the person's own GitHub account."""

import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from starlette.responses import RedirectResponse, Response

from glyphh_server.api.auth import Conn
from glyphh_server.api.browser_session import START_AGAIN, TTL, bind_browser, browser, cfg, forget_browser, new_browser
from glyphh_server.api.pages import to_platform
from glyphh_server.config import Settings
from glyphh_server.errors import Invalid
from glyphh_server.ops import github_installations
from glyphh_server.ops.auth import signed
from glyphh_server.ops.github_app import GitHubApp

router = APIRouter(tags=["github"])

PATH: str = "/v1/github"
LINK: str = "github_install"
STATE: str = "github_state"


def install_link(settings: Settings, user_id: uuid.UUID) -> str:
    value = signed.sign(settings.secret_key, {"k": LINK, "u": str(user_id)}, TTL)
    return f"{settings.base_url}{PATH}/install?{urlencode({'link': value})}"


def _app(request: Request) -> GitHubApp:
    return GitHubApp(request.app.state.http, cfg(request), request.app.state.github_key)


@router.get(f"{PATH}/install", operation_id="gitHubInstallPage", response_class=RedirectResponse, status_code=302)
async def install_page(request: Request, link: str) -> Response:
    """Opened in a browser, from the link: on to GitHub's install page for Glyphh's App."""
    settings = cfg(request)
    _app(request)
    found = signed.verify(settings.secret_key, link)
    if found.get("k") != LINK:
        raise Invalid(START_AGAIN)
    nonce = new_browser()
    state = signed.sign(settings.secret_key, {"k": STATE, "u": found["u"], "n": nonce}, TTL)
    away = RedirectResponse(f"{settings.github_app_install_url}?{urlencode({'state': state})}", status_code=302)
    return bind_browser(away, settings, nonce, PATH)


@router.get(f"{PATH}/callback", operation_id="gitHubInstallCallback", response_class=Response)
async def callback(request: Request, conn: Conn, state: str, installation_id: int | None = None) -> Response:
    """Where GitHub sends the browser back after installing: the installation is recorded for the person, and the
    browser goes on to the platform's `/github?installed=<login>`."""
    app = _app(request)
    st = signed.verify(cfg(request).secret_key, state)
    if st.get("k") != STATE or st["n"] != browser(request):
        raise Invalid(START_AGAIN)
    if installation_id is None:
        raise Invalid("GitHub didn't install the App. Start again in Claude.", reason="not_installed")
    login = await github_installations.record(conn, app, uuid.UUID(st["u"]), installation_id)
    return forget_browser(to_platform(cfg(request), "/github", installed=login), PATH)
