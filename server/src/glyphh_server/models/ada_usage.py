import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class AdaUsage(Base):
    """Ada Cloud's reads an org made in a calendar month (period YYYY-MM, UTC), what its plan's cloud_requests count:
    counted in Redis as they are made and added here by the minute tick (glyphh_ada/usage.py), so losing Redis loses
    at most a minute's count."""

    __tablename__ = "ada_usage"
    __table_args__ = (CheckConstraint("requests >= 0", name="ada_usage_requests"),)

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True)
    period: Mapped[str] = mapped_column(Text, primary_key=True)
    requests: Mapped[int] = mapped_column(BigInteger, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdaMeterEvent(Base):
    """Reads past a metered plan's month (Basic, Pro, Team) reported to Stripe's ada_requests Billing Meter for an org's
    customer, by the month they were made in: written before it is sent, its id the event's identifier, so a send
    retried after a failure is counted once; sent_at once Stripe took it (ops/billing/ada_meter.py)."""

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
