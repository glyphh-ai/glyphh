import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class RuntimeKey(Base):
    """An Ada Cloud API key (`glyphh_ak_…`, glyphh_ada/keys.py), kept as its SHA-256: it calls the Ada API acting in
    its maker's org with its clearance (0 to 1). A key may expire. Revoking one keeps the row, named and dated in its
    maker's list, until they remove it.

    The table's name is from when it also held the keys of self-hosted runtimes; `cloud` is the only scope left."""

    __tablename__ = "runtime_keys"
    __table_args__ = (
        CheckConstraint("scope = 'cloud'", name="runtime_keys_scope"),
        CheckConstraint("clearance >= 0 AND clearance <= 1", name="runtime_keys_clearance"),
    )

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    key_hash: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = created_at()
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str] = mapped_column(Text, server_default="cloud")
    clearance: Mapped[Decimal] = mapped_column(Numeric(4, 3), server_default="1")
