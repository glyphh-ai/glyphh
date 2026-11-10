import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

INTERVALS: tuple[str, ...] = ("month", "year")


class Plan(Base):
    """A plan an org can be on: Free, Basic, Pro, Team, Enterprise (in `sort` order). Retired with active=false,
    never deleted."""

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = guid()
    name: Mapped[str] = mapped_column(Text, unique=True)
    active: Mapped[bool] = mapped_column(server_default="true")
    sort: Mapped[int] = mapped_column(server_default="0")


class PlanVersion(Base):
    """A plan's price, limits and features at one moment. Never changed: a new price is a new version with its own
    Stripe price. A null limit is unlimited. price_cents is a month's or a year's (billing_interval, null when free),
    null when set per customer; self_serve plans are bought through Stripe Checkout, the others by contract.
    max_machines is the org's runtime nodes, its people's together (the licence key's max_nodes); precedents what one
    node may hold across its Ada models (the key's max_precedents). The features are signed into the licence, sync
    as the key's cluster_sync_enabled.

    Ada Cloud's limits (docs/specs/ada-cloud.md, section 7), the org's whatever its people, models or keys:
    cloud_precedents across its models, cloud_requests (reads) a calendar month, cloud_rps calls a second; past
    cloud_requests, cloud_overage meters the rest (Basic, Pro, Team) or the reads are refused until the month turns
    (Free). llm_tokens: the Glyphh-hosted models' tokens a calendar month (docs/specs/tokens.md), past which they
    are charged to the org's overage balance; null, by contract.
    A version that changes only these takes over the Stripe price and the orgs of the one before it (db/seed.py)."""

    __tablename__ = "plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_id", "version", name="plan_versions_version"),
        CheckConstraint("coalesce(price_cents, 0) >= 0", name="plan_versions_price"),
        CheckConstraint(f"billing_interval IN {INTERVALS}", name="plan_versions_interval"),
        CheckConstraint("coalesce(max_machines, 0) >= 0 AND coalesce(precedents, 0) >= 0", name="plan_versions_limits"),
        CheckConstraint(
            "coalesce(cloud_precedents, 0) >= 0 AND coalesce(cloud_requests, 0) >= 0 AND coalesce(cloud_rps, 1) > 0",
            name="plan_versions_cloud",
        ),
        CheckConstraint("coalesce(llm_tokens, 0) >= 0", name="plan_versions_llm"),
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
    cloud_precedents: Mapped[int | None]
    cloud_requests: Mapped[int | None]
    cloud_rps: Mapped[int | None]
    cloud_overage: Mapped[bool] = mapped_column(server_default="false")
    llm_tokens: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = created_at()
