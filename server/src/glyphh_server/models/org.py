import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class Org(Base):
    """A customer org, under Glyphh: the one parent org, the only org with no parent."""

    __tablename__ = "orgs"
    __table_args__ = (
        Index("orgs_one_parent", text("(true)"), unique=True, postgresql_where=text("parent_id IS NULL")),
    )

    id: Mapped[uuid.UUID] = guid()
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orgs.id", ondelete="RESTRICT"))
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
