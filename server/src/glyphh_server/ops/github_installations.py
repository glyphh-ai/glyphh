"""The Glyphh GitHub App on a person's own GitHub account. Installing it goes through the browser; the installation
GitHub sends back is recorded only when GitHub says it is on the GitHub account the person signs in with, so nobody
can record someone else's. From it the server can mint a short-lived token for one of the person's repos."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Forbidden, NotFound
from glyphh_server.models import GitHubInstallation, Identity
from glyphh_server.ops.github_app import GitHubApp
from glyphh_server.ops.guards import taken


class InstallationView(BaseModel):
    installation_id: int
    account_login: str
    created_at: datetime
    removed_at: datetime | None


class RepoToken(BaseModel):
    token: str
    expires_at: datetime


async def github_account(conn: AsyncConnection, user_id: uuid.UUID) -> str:
    """The id of the GitHub account the person signs in with; installing the App needs one."""
    found = select(Identity.provider_user_id).where(Identity.user_id == user_id, Identity.provider == "github")
    account = (await conn.execute(found)).scalar_one_or_none()
    if account is None:
        raise Forbidden("Link GitHub to your Glyphh account first, then install the App.", reason="github_not_linked")
    return account


async def record(conn: AsyncConnection, app: GitHubApp, user_id: uuid.UUID, installation_id: int) -> str:
    """Record the person's installation, once GitHub confirms it is on their own account. Answers its login. One on
    a GitHub organisation is nobody's own: it is not recorded (its repos are connected one by one, each where the
    person may push: ops/projects/github.py), and its login is answered all the same."""
    mine = await github_account(conn, user_id)
    account = (await app.installation(installation_id))["account"]
    if account.get("type") == "Organization":
        return str(account["login"])
    if str(account["id"]) != mine:
        raise Forbidden("That installation is not on the GitHub account you sign in with.", reason="not_yours")
    values = {"user_id": user_id, "installation_id": installation_id, "account_login": account["login"]}
    stmt = upsert(GitHubInstallation).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[GitHubInstallation.user_id],
        set_={"installation_id": installation_id, "account_login": account["login"], "removed_at": None},
    )
    with taken("That installation is recorded for another Glyphh account.", installation_id=installation_id):
        await conn.execute(stmt)
    return str(account["login"])


async def list_installations(conn: AsyncConnection, user_id: uuid.UUID) -> list[InstallationView]:
    rows = await conn.execute(
        select(
            GitHubInstallation.installation_id,
            GitHubInstallation.account_login,
            GitHubInstallation.created_at,
            GitHubInstallation.removed_at,
        ).where(GitHubInstallation.user_id == user_id)
    )
    return [InstallationView(**r._mapping) for r in rows]


async def repo_token(conn: AsyncConnection, app: GitHubApp, user_id: uuid.UUID, repo: str) -> RepoToken:
    """A one-hour, read-only token for one repo (`owner/name`) on the account the person installed the App on."""
    found = select(GitHubInstallation.installation_id, GitHubInstallation.account_login).where(
        GitHubInstallation.user_id == user_id, GitHubInstallation.removed_at.is_(None)
    )
    row = (await conn.execute(found)).first()
    if row is None:
        raise NotFound("Install Glyphh's GitHub App on your GitHub account first.", reason="github_app_missing")
    owner, _, name = repo.partition("/")
    if owner.lower() != row.account_login.lower() or not name or "/" in name:
        raise Forbidden("That repo isn't on the GitHub account Glyphh's App is installed on.", repo=repo)
    minted = await app.repo_token(row.installation_id, name)
    return RepoToken(token=minted["token"], expires_at=minted["expires_at"])
