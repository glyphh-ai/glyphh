"""The crew's project for a workspace (docs/specs/bots.md, 10): the Bots screen never shows or names a project, so
`put` finds the one for a GitHub repo and branch, or makes it, and sets it to the bots and crew settings given: one
per repo and branch for the org, its slug made from the two (`crew-<12 hex>`), its name the repo and branch. It
connects GitHub for the repo as it goes (ops/projects/github.py): refused, with the install link, while Glyphh's
GitHub App is not installed there."""

import hashlib
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import Project
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.projects import store
from glyphh_server.ops.projects.views import (
    MEMBERS_ABOUT,
    MODE_ABOUT,
    NARRATE_ABOUT,
    ORCHESTRATOR_ABOUT,
    REVIEW_ABOUT,
    RUNS_ON_ABOUT,
    SPEND_ABOUT,
    TURNS_ABOUT,
    Branch,
    ProjectIn,
    ProjectPatch,
    ProjectView,
    Review,
    TurnMode,
)

REPO: str = r"^(https://github\.com/)?[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}/?$"
HOST: str = "https://github.com/"
NAME_MAX: int = 80


class CrewIn(BaseModel):
    """The workspace, the bots and the crew settings. A setting left out is left as it is (a new project: its
    default); `runs_on`, `orchestrator` and `max_spend_cents` given as null are cleared."""

    model_config = ConfigDict(extra="forbid")
    repo: str = Field(pattern=REPO, description="The workspace's GitHub repo: owner/name, or its github.com address")
    branch: Branch = Field("main", description="The workspace's branch: each turn starts from it and merges into it")
    members: list[uuid.UUID] = Field(min_length=1, max_length=8, description=MEMBERS_ABOUT)
    runs_on: uuid.UUID | None = Field(None, description=RUNS_ON_ABOUT)
    turn_mode: TurnMode | None = Field(None, description=MODE_ABOUT)
    orchestrator: uuid.UUID | None = Field(None, description=ORCHESTRATOR_ABOUT)
    review: Review | None = Field(None, description=REVIEW_ABOUT)
    narrate: bool | None = Field(None, description=NARRATE_ABOUT)
    max_turns: int | None = Field(None, ge=1, le=200, description=TURNS_ABOUT)
    max_spend_cents: int | None = Field(None, ge=1, le=1_000_000, description=SPEND_ABOUT)


def slug_of(repo: str, branch: str) -> str:
    return "crew-" + hashlib.sha256(f"{repo.lower()}@{branch}".encode()).hexdigest()[:12]


async def put(conn: AsyncConnection, who: Principal, github: Any, body: CrewIn) -> ProjectView:
    repo = body.repo.removeprefix(HOST).rstrip("/")
    installation_id = await github.connect(conn, who.user_id, repo)
    slug = slug_of(repo, body.branch)
    given = body.model_dump(exclude_unset=True, exclude={"repo", "branch"})
    if (await conn.execute(select(Project.id).where(Project.slug == slug))).first() is None:
        named = {"name": f"{repo} ({body.branch})"[:NAME_MAX], "repo_url": HOST + repo, "base_branch": body.branch}
        await store.create(conn, who, ProjectIn(**named, **{k: v for k, v in given.items() if v is not None}), slug)
    else:
        await store.patch(conn, slug, ProjectPatch(**given))
    await conn.execute(update(Project).where(Project.slug == slug).values(github_installation_id=installation_id))
    return await store.one(conn, slug)
