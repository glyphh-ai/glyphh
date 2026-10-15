import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

TOKEN_KINDS: tuple[str, ...] = ("access", "refresh")


class ConnectorToken(Base):
    """A grant's access token (short-lived) or refresh token (rotated: used_at once it has been exchanged), opaque
    and kept only as a hash."""

    __tablename__ = "connector_tokens"
    __table_args__ = (CheckConstraint(f"kind IN {TOKEN_KINDS}", name="connector_tokens_kind"),)

    id: Mapped[uuid.UUID] = guid()
    grant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("connector_grants.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
