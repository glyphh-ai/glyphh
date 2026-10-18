import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, guid

MODES: tuple[str, ...] = ("hosted", "local", "self")


class Rrotor(Base):
    """A person's runtime: one hosted (a Fly machine and its volume, Pro and Team), one local per install that
    started one, keyed by that install, and any self-hosted ones (`self`, on the person's own infrastructure: named,
    at its public address `https://<host>`). Its token (only the hash is kept) signs its outbound link. Region and
    Fly machine are the hosted one's; image_version is what any one last said it runs; a local one has none until it
    links. A self-hosted one's heartbeat leaves its time, the runs in progress and its machine's hash, never its
    caller's address. seq is the last result or event sequence number applied from its link, so a replay is applied
    once."""

    __tablename__ = "rrotors"
    __table_args__ = (
        CheckConstraint(f"mode IN {MODES}", name="rrotors_mode"),
        CheckConstraint("(mode = 'local') = (install_id IS NOT NULL)", name="rrotors_local_install"),
        CheckConstraint("(mode = 'self') = (public_url IS NOT NULL AND name IS NOT NULL)", name="rrotors_self_address"),
        Index("rrotors_one_hosted", "user_id", unique=True, postgresql_where=text("mode = 'hosted'")),
        Index("rrotors_self_url", "user_id", "public_url", unique=True, postgresql_where=text("mode = 'self'")),
        Index("rrotors_self_host", "public_url", postgresql_where=text("mode = 'self'")),
    )

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(Text)
    install_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("installs.id", ondelete="CASCADE"), unique=True)
    fly_machine_id: Mapped[str | None] = mapped_column(Text)
    fly_volume_id: Mapped[str | None] = mapped_column(Text)
    month: Mapped[str | None] = mapped_column(Text)  # the month the tally is of, YYYY-MM
    month_seconds: Mapped[int] = mapped_column(Integer, server_default="0")  # online seconds that month
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # the month's hours spent
    region: Mapped[str | None] = mapped_column(Text)
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
