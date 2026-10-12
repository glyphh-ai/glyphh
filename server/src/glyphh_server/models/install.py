import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base

STATUSES: tuple[str, ...] = ("working", "thinking", "needs_you", "idle", "stuck", "done")


class SuperPowerInstall(Base):
    """A super power installed on a machine, and what it is doing there now: rrotor writes the status when it
    changes. A super power can be installed on many machines."""

    __tablename__ = "super_power_installs"
    __table_args__ = (
        CheckConstraint(f"status IN {STATUSES}", name="super_power_installs_status"),
        Index("super_power_installs_recent", "machine_id", "last_active_at"),
    )

    super_power_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("super_powers.id", ondelete="CASCADE"), primary_key=True
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), index=True)
    status: Mapped[str] = mapped_column(Text, server_default="idle")
    status_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
