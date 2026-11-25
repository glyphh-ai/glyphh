import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at


class OAuthCode(Base):
    """An authorization the person allowed, until its code (only its hash is kept) is redeemed: once, while it lasts,
    by the same client and redirect URI, with the PKCE verifier for its S256 challenge. grant_id names the grant it
    went into, so a second use revokes it."""

    __tablename__ = "oauth_codes"

    code_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    redirect_uri: Mapped[str] = mapped_column(Text)
    code_challenge: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text)
    resource: Mapped[str] = mapped_column(Text)
    grant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("connector_grants.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
