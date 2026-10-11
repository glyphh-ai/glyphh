import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class Token(Base):
    """A sign-in's access and refresh tokens, kept only as hashes. Revoked by setting revoked_at.
    Issued to an agent host when oauth_client_id is set; to the player or rrotor's UI when it is not."""

    __tablename__ = "tokens"

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    oauth_client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True
    )
    access_hash: Mapped[str] = mapped_column(Text, unique=True)
    refresh_hash: Mapped[str] = mapped_column(Text, unique=True)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
