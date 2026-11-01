import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class GitHubInstallation(Base):
    """The Glyphh GitHub App installed on the person's own GitHub account, one per person: the server can mint a
    short-lived token for one repo from it. No long-lived GitHub key is kept."""

    __tablename__ = "github_installations"

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    installation_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    account_login: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
