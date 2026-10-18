import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

INTERVALS: tuple[str, ...] = ("month", "year")


class Plan(Base):
    """A plan an org can be on: Free, Pro, Team, Enterprise. Retired with active=false, never deleted."""

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = guid()
    name: Mapped[str] = mapped_column(Text, unique=True)
    active: Mapped[bool] = mapped_column(server_default="true")
    sort: Mapped[int] = mapped_column(server_default="0")


class PlanVersion(Base):
    """A plan's price, limits and features at one moment. Never changed: a new price is a new version with its own
    Stripe price. A null limit is unlimited. price_cents is a month's or a year's (billing_interval, null when free),
    null when set per customer; self_serve plans are bought through Stripe Checkout, the others by contract.
    max_machines is how many hosted machines the org may have, its people's together (0: none); precedents the
    managed bucket, what a hosted runtime may hold. The features are signed into the licence. hosting_markup_pct is
    added to Fly's rates for the hosted machines and is never shown; null where there is no hosting or it is set per
    customer (an org's own markup_pct overrides it)."""

    __tablename__ = "plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_id", "version", name="plan_versions_version"),
        CheckConstraint("coalesce(price_cents, 0) >= 0", name="plan_versions_price"),
        CheckConstraint(f"billing_interval IN {INTERVALS}", name="plan_versions_interval"),
        CheckConstraint("coalesce(max_machines, 0) >= 0 AND coalesce(precedents, 0) >= 0", name="plan_versions_limits"),
        CheckConstraint("coalesce(hosting_markup_pct, 0) >= 0", name="plan_versions_markup"),
    )

    id: Mapped[uuid.UUID] = guid()
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int]
    stripe_price_id: Mapped[str | None] = mapped_column(Text, unique=True)
    price_cents: Mapped[int | None]
    billing_interval: Mapped[str | None] = mapped_column(Text)
    self_serve: Mapped[bool] = mapped_column(server_default="true")
    max_machines: Mapped[int | None]
    precedents: Mapped[int | None]
    sync: Mapped[bool] = mapped_column(server_default="false")
    ha: Mapped[bool] = mapped_column(server_default="false")
    offline: Mapped[bool] = mapped_column(server_default="false")
    sso: Mapped[bool] = mapped_column(server_default="false")
    hosting_markup_pct: Mapped[int | None]
    created_at: Mapped[datetime] = created_at()
