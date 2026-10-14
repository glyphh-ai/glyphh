import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

SURFACES: tuple[str, ...] = ("desktop", "cli")


class Install(Base):
    """The mod on one machine, made by one device-flow approval. Revoking it signs that machine out."""

    __tablename__ = "installs"
    __table_args__ = (CheckConstraint(f"surface IN {SURFACES}", name="installs_surface"),)

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    surface: Mapped[str] = mapped_column(Text)
    mod_version: Mapped[str] = mapped_column(Text)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
