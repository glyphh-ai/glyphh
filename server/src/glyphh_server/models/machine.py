import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid, updated_at

HOSTS: tuple[str, ...] = ("fly", "aws", "azure", "gcp", "digitalocean", "hetzner", "vps", "docker")
PLATFORMS: tuple[str, ...] = ("macos", "windows", "linux")


class Machine(Base):
    """A registered rrotor: one member's, where it runs, its platform and build, whether it is connected now.
    It connects with its own token and SSH key; only the token's hash is kept."""

    __tablename__ = "machines"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="machines_name_per_owner"),
        CheckConstraint(f"host IN {HOSTS}", name="machines_host"),
        CheckConstraint(f"platform IN {PLATFORMS}", name="machines_platform"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    host: Mapped[str] = mapped_column(Text)
    platform: Mapped[str] = mapped_column(Text)
    version: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    ssh_public_key: Mapped[str] = mapped_column(Text, unique=True)
    ssh_fingerprint: Mapped[str] = mapped_column(Text)
    shell_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    local_ports: Mapped[list[int]] = mapped_column(ARRAY(Integer), server_default=text("'{}'"))
    online: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
