import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class Token(Base):
    """An install's bearer token: opaque, kept only as a hash, revoked with its install."""

    __tablename__ = "tokens"

    id: Mapped[uuid.UUID] = guid()
    install_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("installs.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
