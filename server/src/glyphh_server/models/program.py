"""Programs (docs/specs/programs.md): an org's deterministic workflows, each one `program.py` (its steps the `FLOW`
literal in it) that one bot or several follow; each program's runs; and every run's audit trail, append only."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Identity, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid
from glyphh_server.models.bot import LIVE, RUN_STATUSES

TRIGGERS: tuple[str, ...] = ("person", "schedule", "connector")


class Program(Base):
    __tablename__ = "programs"
    __table_args__ = (
        Index("programs_one_slug", "org_id", "slug", unique=True),
        Index("programs_due", "next_run_at", postgresql_where=text("next_run_at IS NOT NULL")),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, server_default="")
    # the bot whose tools its steps use and who does a step that names no bot
    bot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bots.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(Text)  # program.py: the one source of truth (ops/programs/flow.py)
    template: Mapped[str] = mapped_column(Text, server_default="")  # the template it came with, if any
    runs_on: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rrotors.id", ondelete="SET NULL"))
    schedule: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProgramRun(Base):
    """One run of a program: where it is (`at`), each finished step's result, the question it waits on."""

    __tablename__ = "program_runs"
    __table_args__ = (
        CheckConstraint(f"status IN {RUN_STATUSES}", name="program_runs_status"),
        CheckConstraint(f"trigger IN {TRIGGERS}", name="program_runs_trigger"),
        Index("program_runs_newest", "program_id", "created_at"),
        Index("program_runs_one_live", "program_id", unique=True, postgresql_where=text(f"status IN {LIVE}")),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    program_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    trigger: Mapped[str] = mapped_column(Text, server_default="person")
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    input: Mapped[str] = mapped_column(Text, server_default="")
    at: Mapped[str] = mapped_column(Text, server_default="")  # the step it is at (or stopped at)
    outputs: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    question: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    error: Mapped[str] = mapped_column(Text, server_default="")
    # the person's yes to the tool call it waits at (ops/bots/agent/permit.py's digest), used once
    approvals: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    machine: Mapped[str] = mapped_column(Text, server_default="")  # the machine walking it, so a restart can end it
    created_at: Mapped[datetime] = created_at()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProgramEvent(Base):
    """One line of a run's audit trail: what happened, at which step, done by which bot, for whom."""

    __tablename__ = "program_events"
    __table_args__ = (Index("program_events_of_run", "run_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("program_runs.id", ondelete="CASCADE"))
    at: Mapped[datetime] = created_at()
    kind: Mapped[str] = mapped_column(Text)  # started, step, asked, answered, done, failed, cancelled
    step: Mapped[str] = mapped_column(Text, server_default="")
    title: Mapped[str] = mapped_column(Text, server_default="")
    bot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bots.id", ondelete="SET NULL"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    ok: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    detail: Mapped[str] = mapped_column(Text, server_default="")  # plain words; never what a tool answered
