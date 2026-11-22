"""Swarms (docs/specs/bots.md, 10): a crew of the org's bots taking turns on one GitHub repo, each turn a pull request
the person merges or rejects, run on one of the org's rrotors (glyphh_swarm); a swarm's runs and each run's turns;
and the org's GitHub token, sealed, that the turns push and open pull requests with."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

REVIEWS: tuple[str, ...] = ("each_turn", "auto")
SWARM_RUN_STATUSES: tuple[str, ...] = ("running", "needs_input", "done", "failed")
SWARM_LIVE: tuple[str, ...] = ("running", "needs_input")
TURN_STATUSES: tuple[str, ...] = (
    *("running", "open", "unchanged", "merging", "merged", "conflict", "rejecting", "rejected"),
    *("failed", "cancelled"),
)
JSON_LIST = text("'[]'::jsonb")


class Swarm(Base):
    """The crew (members: bot ids, in speaking order), the repo and its base branch, how many rounds, whether each
    pull request waits for the person (each_turn) or is merged as it opens (auto), and the rrotor it runs on."""

    __tablename__ = "swarms"
    __table_args__ = (
        Index("swarms_one_slug", "org_id", "slug", unique=True),
        CheckConstraint(f"review IN {REVIEWS}", name="swarms_review"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    repo_url: Mapped[str] = mapped_column(Text)  # https://github.com/<owner>/<name>
    base_branch: Mapped[str] = mapped_column(Text, server_default="main")
    members: Mapped[list[str]] = mapped_column(JSONB, server_default=JSON_LIST)
    rounds: Mapped[int] = mapped_column(Integer, server_default="1")
    review: Mapped[str] = mapped_column(Text, server_default="each_turn")
    runs_on: Mapped[uuid.UUID] = mapped_column(ForeignKey("rrotors.id", ondelete="CASCADE"))  # goes with its rrotor
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SwarmRun(Base):
    """One go of a swarm on a task: the crew, rounds and review it began with, its stamp (its branches' suffix), the
    bots in a row that said DONE, and how it stands: running (a call out on the rrotor), needs_input (a pull request
    waits for the person), done or failed."""

    __tablename__ = "swarm_runs"
    __table_args__ = (
        CheckConstraint(f"status IN {SWARM_RUN_STATUSES}", name="swarm_runs_status"),
        Index("swarm_runs_newest", "swarm_id", "created_at"),
        Index("swarm_runs_one_live", "swarm_id", unique=True, postgresql_where=text(f"status IN {SWARM_LIVE}")),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    swarm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("swarms.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    task: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="running")
    members: Mapped[list[str]] = mapped_column(JSONB, server_default=JSON_LIST)
    rounds: Mapped[int] = mapped_column(Integer)
    review: Mapped[str] = mapped_column(Text)
    rrotor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rrotors.id", ondelete="SET NULL"))
    stamp: Mapped[str] = mapped_column(Text)
    done: Mapped[list[str]] = mapped_column(JSONB, server_default=JSON_LIST)  # bot slugs, in a row
    error: Mapped[str] = mapped_column(Text, server_default="")
    created_at: Mapped[datetime] = created_at()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SwarmTurn(Base):
    """One bot's turn: its branch, what it said, its pull request and how that went. call_id is the rrotor run the
    turn waits on (its turn, then its merge or reject); remote_seq the last result taken for it."""

    __tablename__ = "swarm_turns"
    __table_args__ = (
        CheckConstraint(f"status IN {TURN_STATUSES}", name="swarm_turns_status"),
        Index("swarm_turns_of_run", "run_id", "n", unique=True),
        Index("swarm_turns_call", "call_id"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("swarm_runs.id", ondelete="CASCADE"))
    n: Mapped[int] = mapped_column(Integer)
    round: Mapped[int] = mapped_column(Integer)
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


class GitHubKey(Base):
    """The org's GitHub token, sealed: a swarm's turns clone, push and open pull requests with it (sent to the rrotor
    with each call, never kept there). Shown by its last four characters and the account it is."""

    __tablename__ = "github_keys"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True)
    token: Mapped[str] = mapped_column(Text)  # sealed (ops/auth/sealed.py)
    hint: Mapped[str] = mapped_column(Text)
    login: Mapped[str] = mapped_column(Text)
    set_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    set_at: Mapped[datetime] = created_at()
