import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid, updated_at

THREAD_STATUSES: tuple[str, ...] = ("working", "idle", "needs_you", "done", "stuck")


class Thread(Base):
    """One job being worked on a machine, by a crew Glyphh leads or by one super power on its own: its record only.
    Its messages live on the machine and never here. Its links to the schedule that keeps it going and to its runs
    arrive with those tables."""

    __tablename__ = "threads"
    __table_args__ = (
        CheckConstraint(f"status IN {THREAD_STATUSES}", name="threads_status"),
        Index("threads_recent", "machine_id", "archived_at", "last_event_at"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"))
    super_power_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("super_powers.id", ondelete="CASCADE"))
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="idle")
    last_seq: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class ThreadCrew(Base):
    """A super power in a thread's crew. A super power is in many threads at once."""

    __tablename__ = "thread_crew"

    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"), primary_key=True)
    super_power_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("super_powers.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
