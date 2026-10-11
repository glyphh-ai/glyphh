import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid, updated_at


class Plan(Base):
    """What an org pays and the limits it puts on the org. Retired with active=false, never deleted."""

    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="plans_price"),
        CheckConstraint("max_seats > 0 AND rpm_limit > 0 AND tpm_limit > 0", name="plans_limits"),
    )

    id: Mapped[uuid.UUID] = guid()
    name: Mapped[str] = mapped_column(Text, unique=True)
    price_cents: Mapped[int]
    stripe_price_id: Mapped[str | None] = mapped_column(Text, unique=True)
    max_seats: Mapped[int | None]
    rpm_limit: Mapped[int | None]
    tpm_limit: Mapped[int | None]
    active: Mapped[bool] = mapped_column(server_default="true")
    sort: Mapped[int] = mapped_column(server_default="0")
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
