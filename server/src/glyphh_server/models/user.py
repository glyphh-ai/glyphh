import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

ROLES: tuple[str, ...] = ("admin", "member")


class User(Base):
    """A person, in exactly one org, as its admin or a member."""

    __tablename__ = "users"
    __table_args__ = (
        Index("users_email", func.lower(text("email")), unique=True),
        CheckConstraint(f"role IN {ROLES}", name="users_role"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="RESTRICT"), index=True)
    email: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
