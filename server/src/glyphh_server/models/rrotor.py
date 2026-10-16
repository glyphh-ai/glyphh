import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, guid

MODES: tuple[str, ...] = ("hosted", "local")


class Rrotor(Base):
    """A person's runtime: one hosted (a Fly machine and its volume, Pro and Team) and one local per install that
    started one, keyed by that install. Its token (only the hash is kept) signs its outbound link. Region, image
    version and Fly machine are the hosted one's; a local one has none until it links. seq is the last result or event
    sequence number applied from its link, so a replay is applied once."""

    __tablename__ = "rrotors"
    __table_args__ = (
        CheckConstraint(f"mode IN {MODES}", name="rrotors_mode"),
        CheckConstraint("(mode = 'local') = (install_id IS NOT NULL)", name="rrotors_local_install"),
        Index("rrotors_one_hosted", "user_id", unique=True, postgresql_where=text("mode = 'hosted'")),
    )

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(Text)
    install_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("installs.id", ondelete="CASCADE"), unique=True)
    fly_machine_id: Mapped[str | None] = mapped_column(Text)
    fly_volume_id: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)
    image_version: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seq: Mapped[int] = mapped_column(BigInteger, server_default="0")
