import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class Plan(Base):
    """A plan an org can be on: Free, Pro, Team. Retired with active=false, never deleted."""

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = guid()
    name: Mapped[str] = mapped_column(Text, unique=True)
    active: Mapped[bool] = mapped_column(server_default="true")
    sort: Mapped[int] = mapped_column(server_default="0")


class PlanVersion(Base):
    """A plan's price and limits at one moment. Never changed: a new price or limit is a new version with its own
    Stripe price. A null limit is unlimited. runtime_hours is the hosted runtime's running time each month (0: none);
    storage_cents_per_gb its storage rate, every GB billed. all_mods includes every active mod, new ones as they ship;
    otherwise only the free ones."""

    __tablename__ = "plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_id", "version", name="plan_versions_version"),
        CheckConstraint("seat_price_cents >= 0", name="plan_versions_price"),
        CheckConstraint(
            "coalesce(max_members, 1) > 0 AND coalesce(max_installs, 1) > 0 AND coalesce(max_workspaces, 1) > 0",
            name="plan_versions_limits",
        ),
    )

    id: Mapped[uuid.UUID] = guid()
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    version: Mapped[int]
    stripe_price_id: Mapped[str | None] = mapped_column(Text, unique=True)
    seat_price_cents: Mapped[int]
    max_members: Mapped[int | None]
    max_installs: Mapped[int | None]
    max_workspaces: Mapped[int | None]
    runtime_hours: Mapped[int | None]
    storage_cents_per_gb: Mapped[int | None]
    all_mods: Mapped[bool]
    created_at: Mapped[datetime] = created_at()
