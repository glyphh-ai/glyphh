import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, guid

CALLERS: tuple[str, ...] = ("routine", "claude", "panel", "test")


class Run(Base):
    """One call of a program's function on a hosted runtime: who called, the status, the times and the seconds rrotor
    ran, for the log and the hours. Never inputs, outputs or content."""

    __tablename__ = "runs"
    __table_args__ = (CheckConstraint(f"caller IN {CALLERS}", name="runs_caller"),)

    id: Mapped[uuid.UUID] = guid()
    program_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("program_versions.id", ondelete="CASCADE"), index=True
    )
    rrotor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rrotors.id", ondelete="CASCADE"), index=True)
    function: Mapped[str] = mapped_column(Text)
    caller: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seconds: Mapped[int | None]
