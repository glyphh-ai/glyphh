"""Hosted bots (docs/specs/bots.md): an org's connections to other services (each a Pipedream account, signed in on
Pipedream's own page; no sign-in is kept here), its bots (the SDK's bot package: a loop of steps, gates that learn
in Ada, hard limits, its agent's prompt and skills; a look; per connection the tools it may use), each bot's runs, and
the org's own Anthropic API key its bots' agent steps run on."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, LargeBinary, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

# dispatched: sent to the rrotor the bot runs on, its result not back yet
RUN_STATUSES: tuple[str, ...] = ("queued", "running", "dispatched", "needs_input", "done", "failed", "skipped")
LIVE: tuple[str, ...] = ("queued", "running", "dispatched", "needs_input")
PERMISSION_MODES: tuple[str, ...] = ("ask", "connection", "auto")


class Connection(Base):
    """One account of another service (its Pipedream app slug), linked by someone in the org for the org."""

    __tablename__ = "connections"
    __table_args__ = (Index("connections_one_account", "org_id", "account_id", unique=True),)

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    app: Mapped[str] = mapped_column(Text)  # Pipedream's app slug (gmail, slack, ...)
    app_name: Mapped[str] = mapped_column(Text)
    app_icon: Mapped[str] = mapped_column(Text, server_default="")
    account_id: Mapped[str] = mapped_column(Text)  # Pipedream's account id (apn_...)
    label: Mapped[str] = mapped_column(Text, server_default="")  # the account's own name (an email, a workspace)
    # per tool key: allow, ask (a step that uses it waits for the person's yes) or deny; a tool not named asks
    permissions: Mapped[dict[str, str]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = created_at()


class Bot(Base):
    __tablename__ = "bots"
    __table_args__ = (
        Index("bots_one_slug", "org_id", "slug", unique=True),
        Index("bots_due", "next_run_at", postgresql_where=text("next_run_at IS NOT NULL")),
        CheckConstraint(f"permission_mode IN {PERMISSION_MODES}", name="bots_permission_mode"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    slug: Mapped[str] = mapped_column(Text)  # fixed at its making: its Ada models are named by it
    name: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, server_default="")
    look: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))  # its cat's parts
    mascot: Mapped[str] = mapped_column(
        Text, server_default=""
    )  # its own drawn mascot, SVG made safe (ops/bots/svg.py)
    # which tool steps wait for the person: ask (unless allowed), connection (as its connection says), auto (none)
    permission_mode: Mapped[str] = mapped_column(Text, server_default="ask")
    voice: Mapped[str] = mapped_column(Text, server_default="")  # the TTS voice it speaks in (ops/bots/voices.py)
    instructions: Mapped[str] = mapped_column(Text, server_default="")  # its agent's prompt (agent.md's body)
    model: Mapped[str] = mapped_column(Text)  # the Claude model its agent steps run on (ops/bots/prices.py)
    # per connection, the tools it may use: [{"connection_id": "...", "tools": ["gmail-send-email", ...]}]
    scopes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    spec: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))  # bot.json, but its names
    skills: Mapped[dict[str, str]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))  # name: SKILL.md
    state: Mapped[bytes | None] = mapped_column(LargeBinary)  # the runner's runs.sqlite, between runs
    ada_key: Mapped[str] = mapped_column(Text, server_default="")  # its Ada API key, sealed (ops/auth/sealed.py)
    # when it runs on its own, as chosen in plain words (ops/bots/schedule.py), and its next run then (none: off)
    schedule: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # where it runs: one of the org's rrotors, or none for Glyphh cloud
    runs_on: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rrotors.id", ondelete="SET NULL"))
    # the tools it adds to the org's connector, by purpose (ops/bots/exposed.py): its template's, or its own
    connector_tools: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BotRun(Base):
    """One run of a bot: what it was given, its log, its data, the question it waits on, and the tokens it used."""

    __tablename__ = "bot_runs"
    __table_args__ = (
        CheckConstraint(f"status IN {RUN_STATUSES}", name="bot_runs_status"),
        Index("bot_runs_newest", "bot_id", "created_at"),
        Index("bot_runs_one_live", "bot_id", unique=True, postgresql_where=text(f"status IN {LIVE}")),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    input: Mapped[str] = mapped_column(Text, server_default="")
    output: Mapped[str] = mapped_column(Text, server_default="")
    error: Mapped[str] = mapped_column(Text, server_default="")  # why it failed, ended early or was skipped
    log: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))  # each step's data
    # what it waits on (needs_input): question, options, batch, answer_with
    question: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    loop_run: Mapped[str] = mapped_column(Text, server_default="")  # the runner's own id for the run
    input_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    output_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    cost_micros: Mapped[int] = mapped_column(BigInteger, server_default="0")
    own_key: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))  # on the org's own Anthropic key
    # run on one of the org's rrotors (ops/bots/remote.py): which, the last result's seq taken from its link (each
    # applied once), and what the current call began with (tokens in, out; when its run there began to wait; the
    # answer it carries)
    rrotor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rrotors.id", ondelete="SET NULL"))
    remote_seq: Mapped[int] = mapped_column(BigInteger, server_default="0")
    remote: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # the person's yes to the step it waits at, by the tool that step runs, used once (ops/bots/approvals.py)
    approvals: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    machine: Mapped[str] = mapped_column(Text, server_default="")  # the machine running it, so its restart can end it
    created_at: Mapped[datetime] = created_at()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BotKey(Base):
    """The org's own Anthropic API key, sealed: its bots' agent steps run on it, and the org pays Anthropic itself."""

    __tablename__ = "bot_keys"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True)
    anthropic_key: Mapped[str] = mapped_column(Text)  # sealed (ops/auth/sealed.py)
    hint: Mapped[str] = mapped_column(Text)  # its last four characters, to tell keys apart
    set_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    set_at: Mapped[datetime] = created_at()
