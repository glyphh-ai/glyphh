import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at

PROVIDERS: tuple[str, ...] = ("google", "github")


class Identity(Base):
    """A Google or GitHub account a user signs in with, found by the provider's own id, never by email alone."""

    __tablename__ = "identities"
    __table_args__ = (CheckConstraint(f"provider IN {PROVIDERS}", name="identities_provider"),)

    provider: Mapped[str] = mapped_column(Text, primary_key=True)
    provider_user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = created_at()
