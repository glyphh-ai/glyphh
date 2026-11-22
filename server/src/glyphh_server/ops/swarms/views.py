"""What the swarms routes and tools take and answer (docs/specs/bots.md, 10)."""

import re
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

BRANCH: re.Pattern[str] = re.compile(r"^(?!-)(?!.*\.\.)(?!.*//)(?!.*@\{)[A-Za-z0-9._/-]{1,200}(?<![./])$")


def _branch(name: str) -> str:
    """A branch name git takes and glyphh_swarm allows (its BRANCH)."""
    if not BRANCH.fullmatch(name):
        raise ValueError("a branch name is letters, digits and . _ / -, with no .. or //, not ending in . or /")
    return name


Branch = Annotated[str, AfterValidator(_branch)]
Review = Literal["each_turn", "auto"]
REPO_ABOUT: str = "The GitHub repo the crew works in: https://github.com/<owner>/<name>"
MEMBERS_ABOUT: str = "The crew: the org's bots by id, in speaking order (1 to 8)"
REVIEW_ABOUT: str = (
    "each_turn: each pull request waits for the person's merge or reject before the next bot goes; auto: merged as "
    "it opens"
)
RUNS_ON_ABOUT: str = "The org's rrotor the turns run on (GET /v1/bots/places lists them): it needs ANTHROPIC_API_KEY"
REPO_PATTERN: str = r"^https://github\.com/[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}/?$"


class Member(BaseModel):
    id: uuid.UUID
    slug: str
    name: str


class SwarmView(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    repo_url: str = Field(description=REPO_ABOUT)
    base_branch: str
    members: list[Member] = Field(description="The crew in speaking order (a bot deleted since is left out)")
    rounds: int
    review: Review = Field(description=REVIEW_ABOUT)
    runs_on: uuid.UUID = Field(description=RUNS_ON_ABOUT)
    created_at: datetime
    updated_at: datetime


class Swarms(BaseModel):
    swarms: list[SwarmView]


class SwarmIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    repo_url: str = Field(pattern=REPO_PATTERN, description=REPO_ABOUT)
    base_branch: Branch = Field("main", description="The branch each turn starts from and merges into")
    members: list[uuid.UUID] = Field(min_length=1, max_length=8, description=MEMBERS_ABOUT)
    rounds: int = Field(1, ge=1, le=10)
    review: Review = Field("each_turn", description=REVIEW_ABOUT)
    runs_on: uuid.UUID = Field(description=RUNS_ON_ABOUT)


class SwarmPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=80, description="Its name; its slug stays")
    repo_url: str | None = Field(None, pattern=REPO_PATTERN, description=REPO_ABOUT)
    base_branch: Branch | None = None
    members: list[uuid.UUID] | None = Field(None, min_length=1, max_length=8, description=MEMBERS_ABOUT)
    rounds: int | None = Field(None, ge=1, le=10)
    review: Review | None = Field(None, description=REVIEW_ABOUT)
    runs_on: uuid.UUID | None = Field(None, description=RUNS_ON_ABOUT)


class TaskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=1, max_length=20_000, description="What the crew is to do in the repo")


class TurnView(BaseModel):
    n: int = Field(description="The turn's number, counting up across rounds")
    round: int
    bot_id: uuid.UUID | None
    bot_slug: str
    bot_name: str
    branch: str
    status: str = Field(
        description="running, open (its pull request waits), unchanged (no changes, no pull request), merging, "
        "merged, conflict (left open), rejecting, rejected, failed or cancelled"
    )
    said: str = Field(description="What the bot said at the end of its turn")
    title: str
    pr_url: str | None
    number: int | None
    head_sha: str | None
    files: list[dict[str, Any]] = Field(description="What it changed: path, added, removed")
    done: bool = Field(description="It said DONE")
    error: str
    created_at: datetime
    finished_at: datetime | None


class SwarmRunView(BaseModel):
    id: uuid.UUID
    swarm_slug: str
    task: str
    status: str = Field(description="running, needs_input (a pull request waits for the person), done or failed")
    rounds: int
    review: Review
    runs_on: uuid.UUID | None
    error: str
    turns: list[TurnView]
    created_at: datetime
    finished_at: datetime | None


class SwarmRuns(BaseModel):
    runs: list[SwarmRunView]


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: Literal["merge", "reject"] = Field(description="The open pull request merged, or closed")


class GitHubKeyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=500, description="A GitHub token: contents and pull requests, write")


class GitHubKeyView(BaseModel):
    set: bool = Field(description="The org's swarms push and open pull requests with its GitHub token")
    hint: str = Field(description="Its last four characters")
    login: str = Field(description="The GitHub account it is")
    set_at: datetime | None
