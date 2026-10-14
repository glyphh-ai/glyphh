import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at
from glyphh_server.models.install import SURFACES


class DeviceCode(Base):
    """A device-flow sign-in in progress (RFC 8628): the code the mod polls with (only its hash is kept), the code
    the person sees, and what the install will be called. Approval makes the install; the mod's next poll takes its
    token and the row is gone."""

    __tablename__ = "device_codes"
    __table_args__ = (
        CheckConstraint(f"surface IN {SURFACES}", name="device_codes_surface"),
        CheckConstraint("approved_at IS NULL OR denied_at IS NULL", name="device_codes_one_answer"),
    )

    device_code_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    user_code: Mapped[str] = mapped_column(Text, unique=True)
    install_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("installs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    surface: Mapped[str] = mapped_column(Text)
    mod_version: Mapped[str] = mapped_column(Text)
    interval: Mapped[int] = mapped_column(server_default="5")
    polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    denied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
