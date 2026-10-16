from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at

UNLOCK_MODS: tuple[str, ...] = ("drips", "games")


class Unlock(Base):
    """A mod bought once for one machine: recorded from Stripe's finished checkout (a Payment Link's session, its
    metadata naming the mod and `client_reference_id` the mod's own install id), keyed by the session so a replay
    changes nothing; refunded when Stripe says so. No org and no user: the licence is for the install alone."""

    __tablename__ = "unlocks"
    __table_args__ = (
        CheckConstraint(f"mod IN {UNLOCK_MODS}", name="unlocks_mod"),
        Index("ix_unlocks_mod_install", "mod", "install"),
    )

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    mod: Mapped[str] = mapped_column(Text)
    install: Mapped[str] = mapped_column(Text)
    payment_intent_id: Mapped[str | None] = mapped_column(Text, unique=True)
    paid_at: Mapped[datetime] = created_at()
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
