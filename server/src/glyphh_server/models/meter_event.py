import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class MeterEvent(Base):
    """Hosting cents reported to Stripe's Billing Meter for an org's customer: written before it is sent, its id the
    event's identifier, so a send retried after a failure is counted once; sent_at once Stripe took it."""

    __tablename__ = "meter_events"
    __table_args__ = (CheckConstraint("cents > 0", name="meter_events_cents"),)

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    customer: Mapped[str] = mapped_column(Text)
    cents: Mapped[int]
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # the event's timestamp
    created_at: Mapped[datetime] = created_at()
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
