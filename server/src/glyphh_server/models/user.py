import uuid
from datetime import datetime

from sqlalchemy import Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid, updated_at


class User(Base):
    """A person and their profile. Which orgs they are in, and their role in each, are their memberships."""

    __tablename__ = "users"
    __table_args__ = (Index("users_email", func.lower(text("email")), unique=True),)

    id: Mapped[uuid.UUID] = guid()
    email: Mapped[str] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()
