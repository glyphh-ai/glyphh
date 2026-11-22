"""What an installation of Glyphh's GitHub App can see, read with one of its short-lived tokens (ops/github_app.py):
the repos it covers (for a repo picker), a repo's branches, and whether a GitHub account may push to a repo (so a
person connects only a repo they can change themselves). Read only; a failure is Unavailable."""

from typing import Any

import httpx
from pydantic import BaseModel, Field

from glyphh_server.errors import Unavailable

API: str = "https://api.github.com"
PER_PAGE: int = 100
PAGES: int = 3  # of the repos an installation covers
PUSHERS: frozenset[str] = frozenset({"admin", "write"})


class RepoView(BaseModel):
    full_name: str = Field(description="owner/name")
    url: str
    private: bool
    default_branch: str


class Repos(BaseModel):
    account_login: str = Field(description="The GitHub account Glyphh's App is installed on; empty: not installed")
    manage_url: str = Field(description="GitHub's page where the person adds or removes the App's repos")
    repos: list[RepoView] = Field(description="The repos it covers, by name (the first 300)")


class Branches(BaseModel):
    default_branch: str
    branches: list[str] = Field(description="The repo's branches (the first 100)")


async def ask(http: httpx.AsyncClient, token: str, path: str) -> tuple[int, Any]:
    headers = {
        "authorization": f"Bearer {token}",
        "accept": "application/vnd.github+json",
        "x-github-api-version": "2022-11-28",
    }
    try:
        res = await http.get(f"{API}{path}", headers=headers, timeout=30)
        return res.status_code, res.json()
    except (httpx.HTTPError, ValueError) as err:
        raise Unavailable("GitHub didn't answer. Try again.", reason="github") from err


async def must(http: httpx.AsyncClient, token: str, path: str) -> Any:
    status, said = await ask(http, token, path)
    if status != 200:
        raise Unavailable(f"GitHub didn't answer ({status}). Try again.", reason="github", status=status)
    return said


def _repo(r: dict[str, Any]) -> RepoView:
    return RepoView(
        full_name=r["full_name"], url=r["html_url"], private=bool(r["private"]), default_branch=r["default_branch"]
    )


async def repos(http: httpx.AsyncClient, token: str) -> list[RepoView]:
    """The repos the token's installation covers, by name."""
    found: list[RepoView] = []
    for page in range(1, PAGES + 1):
        said = await must(http, token, f"/installation/repositories?per_page={PER_PAGE}&page={page}")
        found += [_repo(r) for r in said["repositories"]]
        if len(said["repositories"]) < PER_PAGE:
            break
    return sorted(found, key=lambda r: r.full_name.lower())


async def branches(http: httpx.AsyncClient, token: str, repo: str) -> Branches:
    about = await must(http, token, f"/repos/{repo}")
    listed = await must(http, token, f"/repos/{repo}/branches?per_page={PER_PAGE}")
    return Branches(default_branch=about["default_branch"], branches=[b["name"] for b in listed])


async def may_push(http: httpx.AsyncClient, token: str, repo: str, login: str, account_id: str) -> bool:
    """GitHub says that account (its login checked against its id) may push to the repo."""
    status, said = await ask(http, token, f"/repos/{repo}/collaborators/{login}/permission")
    if status == httpx.codes.NOT_FOUND:
        return False
    if status != 200:
        raise Unavailable(f"GitHub didn't answer ({status}). Try again.", reason="github", status=status)
    return str(said["user"]["id"]) == account_id and said.get("permission") in PUSHERS
