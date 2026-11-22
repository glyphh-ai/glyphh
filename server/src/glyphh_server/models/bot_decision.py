"""A bot's gates' decisions, one row per item per gate per run (docs/specs/bots.md, 12): what the SDK's runner keeps in
the bot's runs.sqlite, copied here after each go so a person can read, search, sort and page them and train the gate
from them. `label` and `fields` are the item made readable (never raw JSON); `body` is what the search reads."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Computed, DateTime, Double, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, guid

WHO: tuple[str, ...] = ("ada", "you", "default")


class BotDecision(Base):
    __tablename__ = "bot_decisions"
    __table_args__ = (
        Index("bot_decisions_one", "bot_id", "loop_run", "gate", "step", "n", "key", unique=True),
        Index("bot_decisions_newest", "bot_id", "at"),
        Index("bot_decisions_search", "search", postgresql_using="gin"),
        CheckConstraint(f"who IN {WHO}", name="bot_decisions_who"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    bot_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"))
    loop_run: Mapped[str] = mapped_column(Text, server_default="")  # the runner's run id; '' for a case by hand
    gate: Mapped[str] = mapped_column(Text)
    step: Mapped[str] = mapped_column(Text, server_default="")
    n: Mapped[int] = mapped_column(Integer, server_default="0")
    key: Mapped[str] = mapped_column(Text, server_default="")  # the item's key in its run
    kind: Mapped[str] = mapped_column(Text, server_default="gate")  # gate, each, code, or case (added by hand)
    label: Mapped[str] = mapped_column(Text, server_default="")
    fields: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    case: Mapped[Any] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))  # what the gate's Ada model read
    outcome: Mapped[str | None] = mapped_column(Text)  # the gate's call
    who: Mapped[str] = mapped_column(Text, server_default="ada")
    mode: Mapped[str] = mapped_column(Text, server_default="")  # why it was asked (new, few, unsure, audit, shadow)
    p: Mapped[float | None] = mapped_column(Double)  # Ada's probability for its call
    guess: Mapped[str | None] = mapped_column(Text)  # Ada's guess, when the person was asked
    recorded: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))  # a precedent of the gate
    corrected: Mapped[str | None] = mapped_column(Text)  # what it should have been (a relabel, or the world's)
    confirmed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))  # the person said it was right
    precedent: Mapped[str] = mapped_column(Text, server_default="")  # its precedent's id in Ada, when known
    body: Mapped[str] = mapped_column(Text, server_default="")
    search: Mapped[Any] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple'::regconfig, body)", persisted=True), nullable=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
