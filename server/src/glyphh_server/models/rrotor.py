import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

MODES: tuple[str, ...] = ("local", "self")


class Rrotor(Base):
    """A person's runtime, which always runs on their own machines: one local per install that started one, keyed by
    that install, and any self-hosted ones (`self`, on the person's own infrastructure: named, at its public address
    `https://<host>`). Its token (only the hash is kept) signs its outbound link and its heartbeat. image_version is
    what it last said it runs; a local one has none until it links. A self-hosted one's heartbeat leaves its time, the
    runs in progress and its machine's hash, never its caller's address. Any one reports its precedents, its total
    across its Ada models, in its link's usage. seq is the last usage sequence number applied from its link, so a
    replay is applied once."""

    __tablename__ = "rrotors"
    __table_args__ = (
        CheckConstraint(f"mode IN {MODES}", name="rrotors_mode"),
        CheckConstraint("(mode = 'local') = (install_id IS NOT NULL)", name="rrotors_local_install"),
        CheckConstraint("(mode = 'self') = (public_url IS NOT NULL AND name IS NOT NULL)", name="rrotors_self_address"),
        Index("rrotors_self_url", "user_id", "public_url", unique=True, postgresql_where=text("mode = 'self'")),
        Index("rrotors_self_host", "public_url", postgresql_where=text("mode = 'self'")),
    )

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(Text)
    install_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("installs.id", ondelete="CASCADE"), unique=True)
    image_version: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seq: Mapped[int] = mapped_column(BigInteger, server_default="0")
    name: Mapped[str | None] = mapped_column(Text)  # self: what the person called it
    public_url: Mapped[str | None] = mapped_column(Text)  # self: https://<host>, its /mcp the OAuth resource
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    machine_hash: Mapped[str | None] = mapped_column(Text)  # self: the heartbeat's sha256 of its machine
    active_runs: Mapped[int | None] = mapped_column(Integer)  # self: runs in progress at its last heartbeat
    precedents: Mapped[int | None] = mapped_column(BigInteger)  # its total across its Ada models, as it last said
    precedents_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
