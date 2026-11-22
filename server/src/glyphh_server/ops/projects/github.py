"""GitHub for the org's projects, through the Glyphh GitHub App (docs/specs/bots.md, 10): never a token a person
pastes, and none kept. A project records the installation that covers its repo, found when a person connects it (the
crew's project made, or a run started): GitHub must say the App is installed on that repo (else not found, with the
link that installs it) and that the person, by the GitHub account they sign in with, may push to it. Each turn then
gets its own token, minted from that installation for that one repo, for one hour, with contents and pull requests
write and metadata read: on Glyphh cloud for GitHub's API (ops/projects/repo.py), on a rrotor sent with the call for
that turn's clone and push. And the reads for a repo picker: the repos the person's own installation covers, and a
repo's branches."""

import re
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.config import Settings
from glyphh_server.errors import Forbidden, Invalid, NotFound
from glyphh_server.models import GitHubInstallation
from glyphh_server.ops import github_repos
from glyphh_server.ops.github_app import LOOK, TURN, GitHubApp
from glyphh_server.ops.github_installations import github_account
from glyphh_server.ops.github_repos import Branches, Repos

NO_PUSH: str = "You can't push to {repo} on GitHub, so you can't connect it here."
MANAGE: str = "https://github.com/settings/installations/{id}"
_NAME: str = r"(?!\.+(/|$))[A-Za-z0-9_.-]{1,100}"  # an owner or a repo: never `.` or `..`, which a URL would follow
REPO: re.Pattern[str] = re.compile(f"{_NAME}/{_NAME}")


class GitHub:
    def __init__(self, http: httpx.AsyncClient, settings: Settings, key: Any) -> None:
        self.http, self.settings, self.key = http, settings, key

    def app(self) -> GitHubApp:
        return GitHubApp(self.http, self.settings, self.key)

    async def _token(self, app: GitHubApp, installation_id: int, repo: str | None, permissions: dict[str, str]) -> str:
        name = repo.split("/")[1] if repo else None
        try:
            return str((await app.repo_token(installation_id, name, permissions))["token"])
        except NotFound as err:
            raise app.missing(repo or "your GitHub account") from err

    async def connect(self, conn: AsyncConnection, user_id: uuid.UUID, repo: str) -> int:
        """The installation that covers the repo (`owner/name`), once GitHub says this person may push to it."""
        if not REPO.fullmatch(repo):
            raise Invalid("A GitHub repo is owner/name.", reason="repo", repo=repo)
        account = await github_account(conn, user_id)
        app = self.app()
        installation_id = await app.covering(repo)
        token = await self._token(app, installation_id, repo, LOOK)
        if not await github_repos.may_push(self.http, token, repo, await app.login(account), account):
            raise Forbidden(NO_PUSH.format(repo=repo), reason="github_no_write", repo=repo)
        return installation_id

    async def token(self, installation_id: int | None, repo: str) -> str:
        """A turn's token: that one repo, one hour, contents and pull requests write."""
        app = self.app()
        if installation_id is None:
            raise app.missing(repo)
        return await self._token(app, installation_id, repo, TURN)

    async def branches(self, conn: AsyncConnection, user_id: uuid.UUID, repo: str) -> Branches:
        installation_id = await self.connect(conn, user_id, repo)
        token = await self._token(self.app(), installation_id, repo, LOOK)
        return await github_repos.branches(self.http, token, repo)

    async def repos(self, conn: AsyncConnection, user_id: uuid.UUID) -> Repos:
        """The repos the person's own installation covers; none listed when they have not installed the App."""
        mine = (GitHubInstallation.user_id == user_id, GitHubInstallation.removed_at.is_(None))
        found = (await conn.execute(select(GitHubInstallation).where(*mine))).first()
        if found is None:
            return Repos(account_login="", manage_url="", repos=[])
        token = await self._token(self.app(), found.installation_id, None, LOOK)
        return Repos(
            account_login=found.account_login,
            manage_url=MANAGE.format(id=found.installation_id),
            repos=await github_repos.repos(self.http, token),
        )
