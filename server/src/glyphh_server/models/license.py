import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base

TIERS: tuple[str, ...] = ("free", "pro", "team", "enterprise")


class LicenseRecord(Base):
    """A licence key the server signed for an org (rrotor's docs/specs/licensing.md): its id is the payload's
    `license_id`, the other columns the payload's fields as signed, `key` the whole `<payload>.<signature>` string
    as delivered. One is issued at each paid period (Stripe's payment) or Enterprise grant, never on Free; revoked
    when the subscription or grant ends, so it is no longer delivered (the key itself runs to its expires_at on a node
    that holds it)."""

    __tablename__ = "licenses"
    __table_args__ = (
        CheckConstraint(f"tier IN {TIERS}", name="licenses_tier"),
        CheckConstraint("coalesce(max_nodes, 1) >= 1 AND coalesce(max_precedents, 0) >= 0", name="licenses_limits"),
        Index("licenses_newest", "org_id", "issued_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    tier: Mapped[str] = mapped_column(Text)
    max_nodes: Mapped[int | None] = mapped_column(Integer)
    max_precedents: Mapped[int | None] = mapped_column(Integer)
    cluster_sync_enabled: Mapped[bool] = mapped_column(Boolean)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    customer_id: Mapped[str] = mapped_column(Text)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    key: Mapped[str] = mapped_column(Text)
