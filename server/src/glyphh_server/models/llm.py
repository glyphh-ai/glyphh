import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

LEDGER_KINDS: tuple[str, ...] = ("topup", "charge", "grant", "refund")


class LlmLedger(Base):
    """The org's overage balance, entry by entry, in microdollars (1 = $0.000001, so no request's charge rounds to
    nothing; docs/specs/tokens.md): a top-up paid through Stripe Checkout (stripe_ref its session, credited once), a
    grant by Glyphh's staff, a refund, and the charges for hosted-model tokens past the plan's allowance, one entry
    a model a UTC day (period, YYYY-MM-DD) that each request's charge is added to. Money in is positive, out negative;
    the balance is their sum, kept in llm_balances in the same transaction."""

    __tablename__ = "llm_ledger"
    __table_args__ = (
        CheckConstraint(f"kind IN {LEDGER_KINDS}", name="llm_ledger_kind"),
        Index("llm_ledger_newest", "org_id", "at"),
        Index(
            "llm_ledger_charge_day",
            "org_id",
            "model",
            "period",
            unique=True,
            postgresql_where=text("kind = 'charge'"),
        ),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    at: Mapped[datetime] = created_at()
    kind: Mapped[str] = mapped_column(Text)
    amount_micros: Mapped[int] = mapped_column(BigInteger)
    stripe_ref: Mapped[str | None] = mapped_column(Text, unique=True)
    model: Mapped[str | None] = mapped_column(Text)
    period: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)


class LlmBalance(Base):
    """The org's overage balance (the ledger's sum, in microdollars; a request may take it a little below 0, charged
    after its reply) and the allowance its hosted-model tokens used in `period` (YYYY-MM, UTC): (input + output) x
    each model's weight. Locked for each request's accounting, so two at once are counted one after the other."""

    __tablename__ = "llm_balances"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True)
    micros: Mapped[int] = mapped_column(BigInteger, server_default="0")
    period: Mapped[str] = mapped_column(Text, server_default="")
    tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LlmUsageDay(Base):
    """A hosted model's day (UTC) for an org: its tokens in and out, its requests, and what the part past the
    allowance was charged, in microdollars. Written with each request's accounting."""

    __tablename__ = "llm_usage_days"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True)
    model: Mapped[str] = mapped_column(Text, primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    input_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    output_tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    requests: Mapped[int] = mapped_column(BigInteger, server_default="0")
    charged_micros: Mapped[int] = mapped_column(BigInteger, server_default="0")
