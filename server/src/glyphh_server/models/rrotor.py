import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

MODES: tuple[str, ...] = ("hosted", "local", "self")


@dataclass(frozen=True, slots=True)
class Size:
    """A hosted machine's size: its Fly guest (CPU kind, CPUs, memory) and its volume."""

    cpu_kind: str
    cpus: int
    memory_mb: int
    volume_gb: int

    def fields(self) -> dict[str, str | int]:
        return {"cpu_kind": self.cpu_kind, "cpus": self.cpus, "memory_mb": self.memory_mb, "volume_gb": self.volume_gb}

    def said(self) -> str:
        return f"{self.cpu_kind} {self.cpus} CPU, {self.memory_mb // 1024} GB memory, {self.volume_gb} GB disk"


SizeName = Literal["small", "medium", "large"]

# The one table of hosted machine sizes: Fly's guest and volume are made from it.
SIZES: dict[SizeName, Size] = {
    "small": Size("shared", 1, 1024, 3),
    "medium": Size("shared", 2, 4096, 10),
    "large": Size("performance", 2, 8192, 20),
}
SIZES_SAID: str = "; ".join(f"{name}: {size.said()}" for name, size in SIZES.items())


class Rrotor(Base):
    """A person's runtime: any number of hosted ones up to the plan's machines (each a Fly machine and its volume,
    named, of one size, `created_at` ordering them: the first is the oldest), one local per install that started one,
    keyed by that install, and any self-hosted ones (`self`, on the person's own infrastructure: named, at its public
    address `https://<host>`). Its token (only the hash is kept) signs its outbound link. Region and Fly machine are a
    hosted one's; image_version is what any one last said it runs; a local one has none until it links. A self-hosted
    one's heartbeat leaves its time, the runs in progress and its machine's hash, never its caller's address. Any one
    reports its precedents, its total across its Ada models, in its link's usage. seq is
    the last result or event sequence number applied from its link, so a replay is applied once."""

    __tablename__ = "rrotors"
    __table_args__ = (
        CheckConstraint(f"mode IN {MODES}", name="rrotors_mode"),
        CheckConstraint("(mode = 'local') = (install_id IS NOT NULL)", name="rrotors_local_install"),
        CheckConstraint("(mode = 'self') = (public_url IS NOT NULL AND name IS NOT NULL)", name="rrotors_self_address"),
        CheckConstraint("(mode = 'hosted') = (size IS NOT NULL AND name IS NOT NULL)", name="rrotors_hosted_machine"),
        CheckConstraint(f"size IN {tuple(SIZES)}", name="rrotors_size"),
        Index("rrotors_hosted_name", "user_id", "name", unique=True, postgresql_where=text("mode = 'hosted'")),
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
    region: Mapped[str | None] = mapped_column(Text)
    image_version: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seq: Mapped[int] = mapped_column(BigInteger, server_default="0")
    name: Mapped[str | None] = mapped_column(Text)  # hosted and self: what the person called it
    public_url: Mapped[str | None] = mapped_column(Text)  # self: https://<host>, its /mcp the OAuth resource
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    machine_hash: Mapped[str | None] = mapped_column(Text)  # self: the heartbeat's sha256 of its machine
    active_runs: Mapped[int | None] = mapped_column(Integer)  # self: runs in progress at its last heartbeat
    size: Mapped[str | None] = mapped_column(Text)  # hosted: small, medium or large (SIZES)
    precedents: Mapped[int | None] = mapped_column(BigInteger)  # its total across its Ada models, as it last said
    precedents_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
