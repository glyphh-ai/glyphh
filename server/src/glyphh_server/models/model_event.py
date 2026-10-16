import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, guid


class ModelEvent(Base):
    """What a model raised, the routine trigger it fired, and the Claude session that fire started; an event that
    fired no routine has neither."""

    __tablename__ = "model_events"

    id: Mapped[uuid.UUID] = guid()
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), index=True)
    routine_trigger_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("routine_triggers.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(Text)
    session_url: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
