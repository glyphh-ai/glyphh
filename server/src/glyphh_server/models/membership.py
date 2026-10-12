import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at

ROLES: tuple[str, ...] = ("super_admin", "org_admin", "user")


class Membership(Base):
    """A person in an org, with their role there and that org's disabled mark. One per person and org."""

    __tablename__ = "memberships"
    __table_args__ = (CheckConstraint(f"role IN {ROLES}", name="memberships_role"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(Text)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
