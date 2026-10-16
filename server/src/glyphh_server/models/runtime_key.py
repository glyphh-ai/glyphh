import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class RuntimeKey(Base):
    """A key that calls the person's hosted runtime at its own address. Only its SHA-256 is kept; rrotor holds the
    same and checks the bearer itself. A key may expire; an expired one leaves what rrotor holds. Revoking one keeps
    the row (named in the list, dated) and drops its hash from what rrotor holds."""

    __tablename__ = "runtime_keys"

    id: Mapped[uuid.UUID] = guid()
    rrotor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rrotors.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    key_hash: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = created_at()
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # What rrotor reports in `usage`: the calls the key let in, and the last of them.
    calls: Mapped[int] = mapped_column(BigInteger, server_default="0")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
