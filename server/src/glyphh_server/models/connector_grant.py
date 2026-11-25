import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class ConnectorGrant(Base):
    """A client (the desktop, claude.ai, the platform) the person allowed to call the Glyphh connector, for a scope and
    the resource its tokens are bound to. One live grant per person and client; revoking it ends every token it
    holds."""

    __tablename__ = "connector_grants"
    __table_args__ = (
        Index(
            "connector_grants_user_client",
            "user_id",
            "client_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True)
    scope: Mapped[str] = mapped_column(Text)
    resource: Mapped[str] = mapped_column(Text)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
