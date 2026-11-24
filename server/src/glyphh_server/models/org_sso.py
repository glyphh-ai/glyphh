"""An org's single sign-on by OpenID Connect (Enterprise, ops/sso.py): its issuer and client (the secret sealed, never
shown back), the email domains that route a sign-in to it, and whether its people must use it."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at


class OrgSso(Base):
    __tablename__ = "org_sso"

    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), primary_key=True)
    issuer: Mapped[str] = mapped_column(Text)  # as its OpenID configuration names it, no trailing slash
    client_id: Mapped[str] = mapped_column(Text)
    client_secret: Mapped[str] = mapped_column(Text)  # sealed (ops/auth/sealed.py)
    # Its people sign in with it and nothing else: Google or GitHub is refused for them.
    enforced: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SsoDomain(Base):
    """An email domain that is one org's sign-in: a person whose work email is at it signs in there."""

    __tablename__ = "sso_domains"

    domain: Mapped[str] = mapped_column(Text, primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_sso.org_id", ondelete="CASCADE"), index=True)
