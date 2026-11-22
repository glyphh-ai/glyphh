"""Projects (docs/specs/bots.md, 10): a crew of the org's bots, in no order, on one GitHub repo and a set of
instructions, taking turns one at a time (wait your turn, or an orchestrator picks), each turn a pull request, on
Glyphh cloud (the repo through GitHub's API) or on one of the org's rrotors (glyphh_swarm: Claude Code in a checkout);
a project's runs and each run's turns; and a person's marks on the runs in their recents. GitHub is reached through
the Glyphh GitHub App: a project keeps the installation that covers its repo, never a token. A turn's work is on
GitHub (and, for a rrotor's, on the rrotor): its row keeps its status, tokens and pointers (its branch, pull request,
call), and what the bot said at its end."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

REVIEWS: tuple[str, ...] = ("each_turn", "end")
TURN_MODES: tuple[str, ...] = ("wait", "orchestrator")
PROJECT_RUN_STATUSES: tuple[str, ...] = ("running", "needs_input", "done", "failed")
PROJECT_LIVE: tuple[str, ...] = ("running", "needs_input")
TURN_STATUSES: tuple[str, ...] = (
    *("picking", "running", "open", "unchanged", "merging", "merged", "conflict", "rejecting", "rejected"),
    *("failed", "cancelled"),
)
TURN_OUT: tuple[str, ...] = ("picking", "running", "merging", "rejecting")  # a step out (a rrotor's call, a task)
JSON_LIST = text("'[]'::jsonb")


class Project(Base):
    """The crew (members: bot ids, a set), the repo and its base branch, the instructions (given here, and the file
    in the repo every bot reads), how the next turn is taken (wait: whoever has waited longest and has something to
    do; orchestrator: a bot of the crew, or Claude, picks), the safety caps, whether a watched run is narrated, the
    review, and where it runs (runs_on none: Glyphh cloud)."""

    __tablename__ = "projects"
    __table_args__ = (
        Index("projects_one_slug", "org_id", "slug", unique=True),
        CheckConstraint(f"review IN {REVIEWS}", name="projects_review"),
        CheckConstraint(f"turn_mode IN {TURN_MODES}", name="projects_turn_mode"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    repo_url: Mapped[str] = mapped_column(Text)  # https://github.com/<owner>/<name>
    base_branch: Mapped[str] = mapped_column(Text, server_default="main")
    members: Mapped[list[str]] = mapped_column(JSONB, server_default=JSON_LIST)
    review: Mapped[str] = mapped_column(Text, server_default="each_turn")
    runs_on: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rrotors.id", ondelete="SET NULL"))  # none: cloud
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    instructions: Mapped[str] = mapped_column(Text, server_default="")
    instructions_path: Mapped[str] = mapped_column(Text, server_default="PROJECT.md")
    turn_mode: Mapped[str] = mapped_column(Text, server_default="wait")
    orchestrator: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bots.id", ondelete="SET NULL"))
    max_turns: Mapped[int] = mapped_column(Integer, server_default="30")
    max_spend_cents: Mapped[int | None] = mapped_column(Integer)
    narrate: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    # the installation of Glyphh's GitHub App that covers the repo, once a person connected it (ops/projects/github.py)
    github_installation_id: Mapped[int | None] = mapped_column(BigInteger)


class ProjectRun(Base):
    """One go of a project: the task it was given (none: the instructions alone), the crew, review, turn mode and caps
    it began with, its stamp (its branches' suffix), with review end its own branch and the pull request of it all,
    the machine its steps on Glyphh cloud run on, and how it stands: running (a step out), needs_input (a pull request
    waits for the person), done (`ended` says why) or failed."""

    __tablename__ = "project_runs"
    __table_args__ = (
        CheckConstraint(f"status IN {PROJECT_RUN_STATUSES}", name="project_runs_status"),
        Index("project_runs_newest", "project_id", "created_at"),
        Index("project_runs_one_live", "project_id", unique=True, postgresql_where=text(f"status IN {PROJECT_LIVE}")),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    task: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="running")
    members: Mapped[list[str]] = mapped_column(JSONB, server_default=JSON_LIST)
    review: Mapped[str] = mapped_column(Text)
    rrotor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rrotors.id", ondelete="SET NULL"))
    stamp: Mapped[str] = mapped_column(Text)
    done: Mapped[list[str]] = mapped_column(JSONB, server_default=JSON_LIST)  # the bots idle in a row, by slug
    error: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = created_at()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    turn_mode: Mapped[str] = mapped_column(Text, server_default="wait")
    max_turns: Mapped[int] = mapped_column(Integer, server_default="30")
    max_spend_cents: Mapped[int | None] = mapped_column(Integer)
    ended: Mapped[str] = mapped_column(Text, server_default="")
    work_branch: Mapped[str | None] = mapped_column(Text)
    pr_url: Mapped[str | None] = mapped_column(Text)
    number: Mapped[int | None] = mapped_column(Integer)
    on_cloud: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    machine: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)  # this run's model for every step; none: each bot's own
    effort: Mapped[str | None] = mapped_column(Text)  # low, medium or high; none: each bot's own


class ProjectTurn(Base):
    """One turn: picking (the orchestrator choosing who goes; no bot yet), then the bot's: its branch, its pull
    request and how that went, how it was taken (wait or orchestrator), its tokens and what they cost at Anthropic's
    rate. call_id is the rrotor's run the turn waits on (its pick, its turn, then its merge or reject); remote_seq
    the last result taken for it. One turn of a run is out at a time (project_turns_one_out): that is the turn's
    lock. `why` (what the orchestrator said) is kept for a run on Glyphh cloud only."""

    __tablename__ = "project_turns"
    __table_args__ = (
        CheckConstraint(f"status IN {TURN_STATUSES}", name="project_turns_status"),
        Index("project_turns_of_run", "run_id", "n", unique=True),
        Index("project_turns_call", "call_id"),
        Index("project_turns_one_out", "run_id", unique=True, postgresql_where=text(f"status IN {TURN_OUT}")),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("project_runs.id", ondelete="CASCADE"))
    n: Mapped[int] = mapped_column(Integer)
    bot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bots.id", ondelete="SET NULL"))
    bot_slug: Mapped[str] = mapped_column(Text)
    bot_name: Mapped[str] = mapped_column(Text)
    branch: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="running")
    said: Mapped[str] = mapped_column(Text, server_default="")
    title: Mapped[str] = mapped_column(Text, server_default="")
    pr_url: Mapped[str | None] = mapped_column(Text)
    number: Mapped[int | None] = mapped_column(Integer)
    head_sha: Mapped[str | None] = mapped_column(Text)
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=JSON_LIST)
    done: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    error: Mapped[str] = mapped_column(Text, server_default="")
    call_id: Mapped[uuid.UUID] = mapped_column()
    remote_seq: Mapped[int] = mapped_column(BigInteger, server_default="0")
    created_at: Mapped[datetime] = created_at()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    picked_by: Mapped[str] = mapped_column(Text, server_default="wait")
    why: Mapped[str] = mapped_column(Text, server_default="")
    input_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    output_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    cost_micros: Mapped[int] = mapped_column(BigInteger, server_default="0")


class RunMark(Base):
    """A person's own mark on a run in their recents (a bot's run or a project's, by its id): pinned, archived."""

    __tablename__ = "run_marks"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    run_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    pinned: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    archived: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
