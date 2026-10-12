import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base

THEMES: tuple[str, ...] = ("dark", "light", "system")
NOTIFICATIONS: tuple[str, ...] = ("on", "off", "ask")
PERMISSION_MODES: tuple[str, ...] = ("ask", "plan", "accept_edits", "auto")
VOICE_MODES: tuple[str, ...] = ("off", "push_to_talk", "continuous")
PAGE_SIZES: tuple[int, ...] = (10, 25, 50, 100)


class UserSettings(Base):
    """A person's own settings, one row each, made the first time one is changed. A null is the default:
    the platform's own for the theme and the rail, rrotor's for the rest."""

    __tablename__ = "user_settings"
    __table_args__ = (
        CheckConstraint(f"theme IN {THEMES}", name="user_settings_theme"),
        CheckConstraint(f"notifications IN {NOTIFICATIONS}", name="user_settings_notifications"),
        CheckConstraint(f"permission_mode IN {PERMISSION_MODES}", name="user_settings_permission_mode"),
        CheckConstraint(f"voice_mode IN {VOICE_MODES}", name="user_settings_voice_mode"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    theme: Mapped[str] = mapped_column(Text, server_default="system")
    notifications: Mapped[str | None] = mapped_column(Text)
    permission_mode: Mapped[str | None] = mapped_column(Text)
    voice_mode: Mapped[str | None] = mapped_column(Text)
    voice_autoplay: Mapped[bool | None] = mapped_column(Boolean)
    voice_brief: Mapped[bool | None] = mapped_column(Boolean)
    sandbox_strict: Mapped[bool | None] = mapped_column(Boolean)
    allowed_hosts: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    rail_collapsed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    page_sizes: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
