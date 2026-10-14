import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

SURFACES: tuple[str, ...] = ("desktop", "cli")
# The id the mod sends for its machine: a hash of the hardware UUID, or a random id it keeps.
MACHINE_ID: str = r"^[A-Za-z0-9_-]{16,128}$"


class Install(Base):
    """The mod on one machine: a person's active installs are their machines, one each. Signing in again on the
    same machine is the same install. Revoking it signs that machine out and frees the slot."""

    __tablename__ = "installs"
    __table_args__ = (
        CheckConstraint(f"surface IN {SURFACES}", name="installs_surface"),
        Index(
            "installs_user_machine",
            "user_id",
            "machine_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    machine_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    surface: Mapped[str] = mapped_column(Text)
    mod_version: Mapped[str] = mapped_column(Text)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
