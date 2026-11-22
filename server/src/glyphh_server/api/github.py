"""The Glyphh GitHub App, from the API: a link that installs it in the browser, the person's installations, and for a
repo picker the repos their installation covers and a repo's branches (ops/projects/github.py)."""

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.api.github_pages import install_link
from glyphh_server.errors import Unavailable
from glyphh_server.ops import github_installations
from glyphh_server.ops.github_installations import InstallationView
from glyphh_server.ops.github_repos import Branches, Repos

router = APIRouter(prefix="/v1/github", tags=["github"])


class InstallLink(BaseModel):
    url: str = Field(description="Open in a browser within 10 minutes: GitHub's install page, then recorded")


def _github(request: Request) -> Any:
    return request.app.state.bots.projects.github


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


@router.get("/repos", operation_id="listGitHubRepos")
async def list_github_repos(caller: Caller, conn: Conn, request: Request) -> Repos:
    """The repos the person's installation of Glyphh's GitHub App covers, for a repo picker; none, and no account,
    when they have not installed it. A repo of a GitHub organisation is not listed: it is connected by its name."""
    return await _github(request).repos(conn, caller.user_id)  # type: ignore[no-any-return]


@router.get("/repos/{owner}/{repo}/branches", operation_id="listGitHubBranches")
async def list_github_branches(owner: str, repo: str, caller: Caller, conn: Conn, request: Request) -> Branches:
    """A repo's branches, once GitHub says Glyphh's App is installed on it (404 github_app_missing, with
    `install_url`) and the person may push to it (403 github_no_write; 403 github_not_linked with no GitHub
    sign-in)."""
    return await _github(request).branches(conn, caller.user_id, f"{owner}/{repo}")  # type: ignore[no-any-return]
