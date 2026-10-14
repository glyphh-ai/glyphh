import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, guid


class Rrotor(Base):
    """A Pro or Team user's hosted runtime: one Fly machine and its volume, one per user. Its token (only the hash is
    kept) signs its outbound link. A local runtime is not here beyond its install."""

    __tablename__ = "rrotors"

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    fly_machine_id: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str] = mapped_column(Text)
    image_version: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
