"""The org's GitHub token for its swarms (docs/specs/bots.md, 10): a swarm's turns clone its repo, push each turn's
branch and open, merge or close its pull request with it, on the rrotor (sent with each call, in git's environment
there, never kept). The org saves it here, sealed (ops/auth/sealed.py), as it saves its Anthropic key: a GitHub token
the person makes (a fine-grained one: the repos, contents and pull requests, read and write), tried with GitHub
before it is kept and shown only by its last four characters and the account it is.

Why not the org's GitHub connection (Pipedream): Pipedream runs a connection's actions and proxies its requests, but
gives no token out for an account signed in with its own OAuth app, and git on the rrotor needs one. Why not the
Glyphh GitHub App: it is installed per person, and mints read-only tokens."""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid, NotFound
from glyphh_server.models import GitHubKey
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.sealed import seal, unseal
from glyphh_server.ops.swarms.views import GitHubKeyView

USER: str = "https://api.github.com/user"
NO_KEY: str = (
    "Save the org's GitHub token first (PUT /v1/github-key): a swarm's turns push and open pull requests with it."
)
Check = Callable[[str], Awaitable[str]]  # a token tried with GitHub: the account's login, or Invalid


def checker(http: httpx.AsyncClient) -> Check:
    async def check(token: str) -> str:
        headers = {"authorization": f"Bearer {token}", "accept": "application/vnd.github+json"}
        try:
            res = await http.get(USER, headers=headers)
        except httpx.HTTPError as err:
            raise Invalid("GitHub did not answer: try again.", reason="token") from err
        if res.status_code != 200:
            raise Invalid("GitHub does not take that token.", reason="token")
        return str(res.json().get("login") or "")

    return check


def view(row: Any) -> GitHubKeyView:
    if row is None:
        return GitHubKeyView(set=False, hint="", login="", set_at=None)
    return GitHubKeyView(set=True, hint=row.hint, login=row.login, set_at=row.set_at)


async def get(conn: AsyncConnection) -> Any:
    return (await conn.execute(select(GitHubKey))).first()


async def token(conn: AsyncConnection, secret: str) -> str:
    """The org's token, opened; NotFound says to save one."""
    found = await get(conn)
    if found is None:
        raise NotFound(NO_KEY, reason="github_key")
    return unseal(secret, found.token)


async def put(conn: AsyncConnection, who: Principal, secret: str, given: str, check: Check) -> GitHubKeyView:
    given = given.strip()
    login = await check(given)
    values = {"org_id": who.org_id, "token": seal(secret, given), "hint": given[-4:], "login": login}
    values["set_by"] = who.user_id
    kept = insert(GitHubKey).values(**values)
    await conn.execute(
        kept.on_conflict_do_update(index_elements=[GitHubKey.org_id], set_={**values, "set_at": func.now()})
    )
    return view(await get(conn))


async def remove(conn: AsyncConnection, org_id: Any) -> GitHubKeyView:
    await conn.execute(delete(GitHubKey).where(GitHubKey.org_id == org_id))
    return view(None)
