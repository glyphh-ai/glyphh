import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class OAuthClient(Base):
    """An agent host (Claude, Codex, ...) that signs members in to Glyphh's MCP server."""

    __tablename__ = "oauth_clients"
    __table_args__ = (CheckConstraint("cardinality(redirect_uris) > 0", name="oauth_clients_redirects"),)

    id: Mapped[uuid.UUID] = guid()
    client_id: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = created_at()


class OAuthCode(Base):
    """A one-time code a member approved for a host: works once, for a minute, only with its PKCE verifier."""

    __tablename__ = "oauth_codes"
    __table_args__ = (CheckConstraint("length(code_challenge) >= 43", name="oauth_codes_pkce"),)

    id: Mapped[uuid.UUID] = guid()
    oauth_client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"))
    code_hash: Mapped[str] = mapped_column(Text, unique=True)
    redirect_uri: Mapped[str] = mapped_column(Text)
    code_challenge: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
