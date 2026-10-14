import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, guid


class ConnectorGrant(Base):
    """A Claude (a routine, the desktop, claude.ai) the person allowed to call the Glyphh connector: its token kept
    only as a hash, revocable one by one."""

    __tablename__ = "connector_grants"

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    client: Mapped[str] = mapped_column(Text)
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
