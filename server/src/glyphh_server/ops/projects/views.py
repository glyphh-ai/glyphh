"""What the projects routes and tools take and answer (docs/specs/bots.md, 10)."""

import re
import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

BRANCH: re.Pattern[str] = re.compile(r"^(?!-)(?!.*\.\.)(?!.*//)(?!.*@\{)[A-Za-z0-9._/-]{1,200}(?<![./])$")
PATH: re.Pattern[str] = re.compile(r"^(?![/.])(?!.*\.\.)(?!.*//)[A-Za-z0-9._/ -]{1,200}(?<![/ ])$")


def _branch(name: str) -> str:
    """A branch name git takes and glyphh_swarm allows (its BRANCH)."""
    if not BRANCH.fullmatch(name):
        raise ValueError("a branch name is letters, digits and . _ / -, with no .. or //, not ending in . or /")
    return name


def _path(name: str) -> str:
    if not PATH.fullmatch(name):
        raise ValueError("a file's path in the repo: letters, digits, spaces and . _ / -, from the repo's root")
    return name


Branch = Annotated[str, AfterValidator(_branch)]
RepoPath = Annotated[str, AfterValidator(_path)]
Review = Literal["each_turn", "end"]
TurnMode = Literal["wait", "orchestrator"]
Effort = Literal["low", "medium", "high"]
MODEL_ABOUT: str = "This run's model for every step (GET /v1/bots/models); none: each bot's own"
EFFORT_ABOUT: str = "This run's effort for every step: low, medium or high; none: each bot's own"
REPO_ABOUT: str = "The GitHub repo the crew works in: https://github.com/<owner>/<name>"
MEMBERS_ABOUT: str = "The crew: the org's bots by id, in no order (1 to 8)"
BRIEF_ABOUT: str = "The project's instructions, given here: every bot reads them, and the repo, on its turn"
PATH_ABOUT: str = "The file in the repo that holds more of its instructions, read on every turn when it is there"
MODE_ABOUT: str = (
    "How the next turn is taken. wait (wait your turn): one bot at a time, the bot that has waited longest and has "
    "something to do; orchestrator: the orchestrator reads the repo and the instructions and names the next bot"
)
ORCHESTRATOR_ABOUT: str = (
    "The org's orchestrator bot: it picks who goes next with turn_mode orchestrator. "
    "Never chosen: one given is not read"
)
REVIEW_ABOUT: str = (
    "each_turn: each pull request waits for the person's merge or reject before the next turn; end: the turns merge "
    "into the run's own branch as they go, and one pull request of it all waits for the person at the end"
)
RUNS_ON_ABOUT: str = (
    "Where its turns run (GET /v1/bots/places): none, Glyphh cloud (bots read and change files and open pull "
    "requests, but run no commands, tests or browser); or the org's rrotor (Claude Code in a checkout; it needs "
    "ANTHROPIC_API_KEY)"
)
TURNS_ABOUT: str = "The safety cap: a run ends once it has taken this many turns"
SPEND_ABOUT: str = "The safety cap: a run ends once its turns' tokens cost this much at Anthropic's rate; none: no cap"
NARRATE_ABOUT: str = "Narrate when watched: a turn is read aloud only while someone has the project open"
REPO_PATTERN: str = r"^https://github\.com/[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}/?$"


class Member(BaseModel):
    id: uuid.UUID
    slug: str
    name: str


class ProjectView(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    repo_url: str = Field(description=REPO_ABOUT)
    base_branch: str
    members: list[Member] = Field(description="The crew, in no order (a bot deleted since is left out)")
    instructions: str = Field(description=BRIEF_ABOUT)
    instructions_path: str = Field(description=PATH_ABOUT)
    turn_mode: TurnMode = Field(description=MODE_ABOUT)
    orchestrator: uuid.UUID | None = Field(description=ORCHESTRATOR_ABOUT)
    review: Review = Field(description=REVIEW_ABOUT)
    runs_on: uuid.UUID | None = Field(description=RUNS_ON_ABOUT)
    max_turns: int = Field(description=TURNS_ABOUT)
    max_spend_cents: int | None = Field(description=SPEND_ABOUT)
    narrate: bool = Field(description=NARRATE_ABOUT)
    github_connected: bool = Field(description="Glyphh's GitHub App is connected for its repo (a run connects it)")
    created_at: datetime
    updated_at: datetime


class Projects(BaseModel):
    projects: list[ProjectView]


class ProjectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    repo_url: str = Field(pattern=REPO_PATTERN, description=REPO_ABOUT)
    base_branch: Branch = Field("main", description="The branch each turn starts from and merges into")
    members: list[uuid.UUID] = Field(min_length=1, max_length=8, description=MEMBERS_ABOUT)
    instructions: str = Field("", max_length=20_000, description=BRIEF_ABOUT)
    instructions_path: RepoPath = Field("PROJECT.md", description=PATH_ABOUT)
    turn_mode: TurnMode = Field("wait", description=MODE_ABOUT)
    orchestrator: uuid.UUID | None = Field(None, description=ORCHESTRATOR_ABOUT)
    review: Review = Field("each_turn", description=REVIEW_ABOUT)
    runs_on: uuid.UUID | None = Field(None, description=RUNS_ON_ABOUT)
    max_turns: int = Field(30, ge=1, le=200, description=TURNS_ABOUT)
    max_spend_cents: int | None = Field(None, ge=1, le=1_000_000, description=SPEND_ABOUT)
    narrate: bool = Field(False, description=NARRATE_ABOUT)


class ProjectPatch(BaseModel):
    """What is given is changed; `runs_on` and `max_spend_cents` given as null are cleared."""

    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=80, description="Its name; its slug stays")
    repo_url: str | None = Field(None, pattern=REPO_PATTERN, description=REPO_ABOUT)
    base_branch: Branch | None = None
    members: list[uuid.UUID] | None = Field(None, min_length=1, max_length=8, description=MEMBERS_ABOUT)
    instructions: str | None = Field(None, max_length=20_000, description=BRIEF_ABOUT)
    instructions_path: RepoPath | None = Field(None, description=PATH_ABOUT)
    turn_mode: TurnMode | None = Field(None, description=MODE_ABOUT)
    orchestrator: uuid.UUID | None = Field(None, description=ORCHESTRATOR_ABOUT)
    review: Review | None = Field(None, description=REVIEW_ABOUT)
    runs_on: uuid.UUID | None = Field(None, description=RUNS_ON_ABOUT)
    max_turns: int | None = Field(None, ge=1, le=200, description=TURNS_ABOUT)
    max_spend_cents: int | None = Field(None, ge=1, le=1_000_000, description=SPEND_ABOUT)
    narrate: bool | None = Field(None, description=NARRATE_ABOUT)


class TaskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field("", max_length=20_000, description="What the crew is to do now; none: its instructions alone")
    model: str | None = Field(None, description=MODEL_ABOUT)
    effort: Effort | None = Field(None, description=EFFORT_ABOUT)


class TurnView(BaseModel):
    n: int = Field(description="The turn's number, counting up")
    bot_id: uuid.UUID | None
    bot_slug: str = Field(description="The bot whose turn it is; empty while the orchestrator is picking")
    bot_name: str
    branch: str
    status: str = Field(
        description="picking (the orchestrator is choosing who goes), running, open (its pull request waits), "
        "unchanged (no changes, no pull request), merging, merged, conflict (left open), rejecting, rejected, "
        "failed or cancelled"
    )
    picked_by: TurnMode = Field(description="How the turn was taken: wait your turn, or the orchestrator's choice")
    why: str = Field(description="What the orchestrator said when it chose (a run on Glyphh cloud; else empty)")
    said: str = Field(description="What the bot said at the end of its turn")
    title: str
    pr_url: str | None
    number: int | None
    head_sha: str | None
    files: list[dict[str, Any]] = Field(description="What it changed: path, added, removed")
    done: bool = Field(description="It said DONE")
    error: str
    input_tokens: int
    output_tokens: int
    cost_micros: int = Field(description="Its tokens at Anthropic's rate, microdollars (what the spend cap counts)")
    created_at: datetime
    finished_at: datetime | None


class ProjectRunView(BaseModel):
    id: uuid.UUID
    project_slug: str
    task: str
    status: str = Field(description="running, needs_input (a pull request waits for the person), done or failed")
    ended: str = Field(
        description="Why a done run ended: done (the crew said so), orchestrator (it said so), max_turns or "
        "max_spend (a safety cap); else empty"
    )
    turn_mode: TurnMode
    review: Review
    runs_on: uuid.UUID | None = Field(description="The rrotor it runs on; none: Glyphh cloud")
    max_turns: int
    max_spend_cents: int | None
    model: str | None = Field(description=MODEL_ABOUT)
    effort: Effort | None = Field(description=EFFORT_ABOUT)
    work_branch: str | None = Field(description="With review end: the run's own branch its turns merge into")
    pr_url: str | None = Field(description="With review end: the pull request of the whole run, once it is open")
    number: int | None
    error: str
    turns: list[TurnView]
    input_tokens: int
    output_tokens: int
    cost_micros: int
    created_at: datetime
    finished_at: datetime | None


class ProjectRuns(BaseModel):
    runs: list[ProjectRunView]


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: Literal["merge", "reject"] = Field(description="The open pull request merged, or closed")
