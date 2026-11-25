import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

AUTH_METHODS: tuple[str, ...] = ("none", "client_secret_post", "client_secret_basic")


class OAuthClient(Base):
    """An MCP client registered with the connector's authorization server (RFC 7591): its exact redirect URIs, and a
    confidential client's secret only as a hash. Belongs to no org; the id is the client_id."""

    __tablename__ = "oauth_clients"
    __table_args__ = (
        CheckConstraint(f"auth_method IN {AUTH_METHODS}", name="oauth_clients_auth_method"),
        CheckConstraint("(auth_method = 'none') = (secret_hash IS NULL)", name="oauth_clients_secret"),
        CheckConstraint("cardinality(redirect_uris) > 0", name="oauth_clients_redirect_uris"),
    )

    id: Mapped[uuid.UUID] = guid()
    name: Mapped[str] = mapped_column(Text)
    redirect_uris: Mapped[list[str]] = mapped_column(ARRAY(Text))
    auth_method: Mapped[str] = mapped_column(Text)
    secret_hash: Mapped[str | None] = mapped_column(Text)
    grant_types: Mapped[list[str]] = mapped_column(ARRAY(Text))
    created_at: Mapped[datetime] = created_at()
