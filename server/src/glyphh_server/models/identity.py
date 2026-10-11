import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

PROVIDERS: tuple[str, ...] = ("google", "github")


class SignInIdentity(Base):
    """A Google or GitHub account a user signs in with, found by the provider's own id, never by email alone."""

    __tablename__ = "sign_in_identities"
    __table_args__ = (
        CheckConstraint(f"provider IN {PROVIDERS}", name="sign_in_identities_provider"),
        UniqueConstraint("provider", "subject", name="sign_in_identities_subject"),
    )

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
