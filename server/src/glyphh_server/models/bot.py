"""Hosted bots (docs/specs/bots.md): an org's connections to other services (each a Pipedream account, signed in on
Pipedream's own page; no sign-in is kept here), its bots (a Claude agent with instructions, a look, the Ada models it
may ask and, per connection, the tools it may use) and each bot's runs, billed by the tokens they use."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

RUN_STATUSES: tuple[str, ...] = ("queued", "running", "done", "failed")


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
    created_at: Mapped[datetime] = created_at()


class Bot(Base):
    __tablename__ = "bots"
    __table_args__ = (Index("bots_one_slug", "org_id", "slug", unique=True),)

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, server_default="")
    look: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))  # its cat's parts
    instructions: Mapped[str] = mapped_column(Text, server_default="")
    model: Mapped[str] = mapped_column(Text)  # the Claude model it runs on (ops/bots/prices.py)
    models: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))  # Ada models it may ask
    # per connection, the tools it may use: [{"connection_id": "...", "tools": ["gmail-send-email", ...]}]
    scopes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    max_turns: Mapped[int] = mapped_column(Integer, server_default="20")
    usd_per_run_micros: Mapped[int] = mapped_column(BigInteger, server_default="2000000")
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BotRun(Base):
    """One run of a bot: what it was given, each step it took, what it answered, and the tokens it used."""

    __tablename__ = "bot_runs"
    __table_args__ = (
        CheckConstraint(f"status IN {RUN_STATUSES}", name="bot_runs_status"),
        Index("bot_runs_newest", "bot_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    input: Mapped[str] = mapped_column(Text, server_default="")
    output: Mapped[str] = mapped_column(Text, server_default="")
    error: Mapped[str] = mapped_column(Text, server_default="")
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    input_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    output_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    cost_micros: Mapped[int] = mapped_column(BigInteger, server_default="0")
    machine: Mapped[str] = mapped_column(Text, server_default="")  # the machine running it, so its restart can end it
    created_at: Mapped[datetime] = created_at()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
