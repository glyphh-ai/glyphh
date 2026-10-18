import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

BILLING_STATUSES: tuple[str, ...] = (
    "none",
    "active",
    "trialing",
    "past_due",
    "unpaid",
    "canceled",
    "incomplete",
    "incomplete_expired",
    "paused",
)


class Org(Base):
    """A team: its plan version, its admin (who handles all billing), and what Stripe says it pays for."""

    __tablename__ = "orgs"
    __table_args__ = (CheckConstraint(f"billing_status IN {BILLING_STATUSES}", name="orgs_billing_status"),)

    id: Mapped[uuid.UUID] = guid()
    name: Mapped[str] = mapped_column(Text)
    plan_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plan_versions.id", ondelete="RESTRICT"), index=True)
    # Set right after the admin's user row exists: the two rows point at each other.
    admin_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL", use_alter=True, name="orgs_admin_user_id_fkey")
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(Text, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text, unique=True)
    billing_status: Mapped[str] = mapped_column(Text, server_default="none")
    # When the subscription renews, from Stripe; empty when not subscribed or ending at the period's end.
    renews_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
