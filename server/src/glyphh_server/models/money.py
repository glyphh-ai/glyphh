"""The money the retired products left on record (2026-11-18). Nothing sells any more; these rows are what was
billed, paid and is still held, kept so each can be settled and shown to staff."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

LEDGER_KINDS: tuple[str, ...] = ("topup", "charge", "grant", "refund")


class AdaMeterEvent(Base):
    """Ada Cloud's reads past a metered plan's month, as each was reported to Stripe's meter for an org's customer:
    what an overage line on an invoice was made of. A record only: nothing writes it any more, and the staff
    dashboard adds up the month's (admin/money.py)."""

    __tablename__ = "ada_meter_events"
    __table_args__ = (CheckConstraint("requests > 0", name="ada_meter_events_requests"),)

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    customer: Mapped[str] = mapped_column(Text)
    period: Mapped[str] = mapped_column(Text)
    requests: Mapped[int]
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # the event's timestamp
    created_at: Mapped[datetime] = created_at()
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LlmLedger(Base):
    """An org's prepaid balance, entry by entry, in microdollars (1 = $0.000001): a top-up paid through Stripe
    Checkout (stripe_ref its session, credited once), a grant by Glyphh's staff, a refund, and the charges the hosted
    models made. Money in is positive, out negative; the balance is their sum, kept in llm_balances in the same
    transaction. Only a top-up paid late is still written (ops/billing/topup.py)."""

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
    """An org's prepaid balance: the ledger's sum, in microdollars. One above zero is money held for a customer, owed
    back (`python -m glyphh_server.winddown counts` says how many and how much). `period` and `tokens` were the
    month's allowance used, no longer read."""

    __tablename__ = "llm_balances"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True)
    micros: Mapped[int] = mapped_column(BigInteger, server_default="0")
    period: Mapped[str] = mapped_column(Text, server_default="")
    tokens: Mapped[int] = mapped_column(BigInteger, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
