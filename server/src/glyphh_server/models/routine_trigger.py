import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

TRIGGER_STATUSES: tuple[str, ...] = ("ok", "broken")


class RoutineTrigger(Base):
    """A Claude routine's API trigger the person let Glyphh fire: its fire URL and its token, the token encrypted with
    the server's secrets key and never shown again. Broken when Anthropic refuses the token (401)."""

    __tablename__ = "routine_triggers"
    __table_args__ = (CheckConstraint(f"status IN {TRIGGER_STATUSES}", name="routine_triggers_status"),)

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    program_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("programs.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(Text)
    fire_url: Mapped[str] = mapped_column(Text)
    token_enc: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="ok")
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
