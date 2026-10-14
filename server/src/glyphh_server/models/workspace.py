import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at


class Workspace(Base):
    """A workspace's name, for the plan's limit. Everything else about it stays in the local rrotor."""

    __tablename__ = "workspaces"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(Text, primary_key=True)
    created_at: Mapped[datetime] = created_at()
