import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class RuntimeKey(Base):
    """A key that calls one of the person's runtimes at its own address: the hosted machine or self-hosted runtime
    it names, or, naming none, every hosted machine of theirs. Only its SHA-256 is kept; rrotor holds the
    same and checks the bearer itself. A key may expire; an expired one leaves what rrotor holds. Revoking one keeps
    the row (named in the list, dated) and drops its hash from what rrotor holds.

    A key of scope `cloud` is an Ada Cloud API key instead (glyphh_ak_, glyphh_ada/keys.py): it calls the Ada API in
    its maker's org with its clearance (0 to 1), and is never sent to a runtime."""

    __tablename__ = "runtime_keys"
    __table_args__ = (
        CheckConstraint("scope IN ('runtime', 'cloud')", name="runtime_keys_scope"),
        CheckConstraint("clearance >= 0 AND clearance <= 1", name="runtime_keys_clearance"),
    )

    id: Mapped[uuid.UUID] = guid()
    rrotor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("rrotors.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    key_hash: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = created_at()
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # What rrotor reports in `usage`: the calls the key let in, and the last of them.
    calls: Mapped[int] = mapped_column(BigInteger, server_default="0")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str] = mapped_column(Text, server_default="runtime")
    clearance: Mapped[Decimal] = mapped_column(Numeric(4, 3), server_default="1")
