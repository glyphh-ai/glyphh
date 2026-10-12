import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid, updated_at

EFFORTS: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")
SP_ROLES: tuple[str, ...] = ("orchestrator", "worker")


class SuperPower(Base):
    """One user's super power: who it is (name, face, character), what it does, and how it runs. Its loop and
    voice columns arrive with the powers they point at; its data lives in rrotor, in a schema of its own."""

    __tablename__ = "super_powers"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="super_powers_name_per_owner"),
        CheckConstraint("avatar_variant BETWEEN 1 AND 16", name="super_powers_avatar_variant"),
        CheckConstraint(
            "personality BETWEEN 1 AND 5 AND directness BETWEEN 1 AND 5 AND temperament BETWEEN 1 AND 5",
            name="super_powers_character",
        ),
        CheckConstraint(f"effort IN {EFFORTS}", name="super_powers_effort"),
        CheckConstraint(f"role IN {SP_ROLES}", name="super_powers_role"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    data_schema: Mapped[str | None] = mapped_column(Text)
    data_role: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default="")
    instructions: Mapped[str] = mapped_column(Text, server_default="")
    avatar_variant: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    avatar_color: Mapped[str | None] = mapped_column(Text)
    avatar_key: Mapped[str | None] = mapped_column(Text)
    personality: Mapped[int] = mapped_column(Integer, server_default=text("3"))
    directness: Mapped[int] = mapped_column(Integer, server_default=text("3"))
    temperament: Mapped[int] = mapped_column(Integer, server_default=text("3"))
    effort: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, server_default="worker")
    live: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    map_layout: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    glyphh: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    voice_id: Mapped[str | None] = mapped_column(Text)
    voice_name: Mapped[str | None] = mapped_column(Text)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    bundle_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
