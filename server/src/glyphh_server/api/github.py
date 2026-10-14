"""The Glyphh GitHub App, from the API: a link that installs it in the browser, and the person's installations."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.api.github_pages import install_link
from glyphh_server.errors import Unavailable
from glyphh_server.ops import github_installations
from glyphh_server.ops.github_installations import InstallationView

router = APIRouter(prefix="/v1/github", tags=["github"])


class InstallLink(BaseModel):
    url: str = Field(description="Open in a browser within 10 minutes: GitHub's install page, then recorded")


@router.post("/install", operation_id="gitHubInstallLink")
async def github_install_link(caller: Caller, conn: Conn, request: Request) -> InstallLink:
    """A link that installs Glyphh's GitHub App on the GitHub account the person signs in with."""
    settings = request.app.state.settings
    if not settings.github_app_configured:
        raise Unavailable("GitHub isn't set up on this server.", reason="github_off")
    await github_installations.github_account(conn, caller.user_id)
    return InstallLink(url=install_link(settings, caller.user_id))


@router.get("/installations", operation_id="listGitHubInstallations")
async def list_github_installations(caller: Caller, conn: Conn) -> list[InstallationView]:
    """Where the person installed Glyphh's GitHub App: at most one account."""
    return await github_installations.list_installations(conn, caller.user_id)
