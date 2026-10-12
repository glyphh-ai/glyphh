import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

INVITE_ROLES: tuple[str, ...] = ("org_admin", "user")


class Invite(Base):
    """An invitation into an org, by email, with the role the person will have. Its link carries a token
    (only the hash is kept). An open invite holds a seat; one open invite per email per org."""

    __tablename__ = "invites"
    __table_args__ = (
        CheckConstraint(f"role IN {INVITE_ROLES}", name="invites_role"),
        Index(
            "invites_one_open",
            "org_id",
            func.lower(text("email")),
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND declined_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
