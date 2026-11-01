"""The catalogue (docs/specs/artifacts.md, 3): one row per app on an org's rrotor, filled from the rrotor's own
`deployed` message up the link and reviewed here. Never the page itself."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid

STATES: tuple[str, ...] = ("draft", "approved", "rejected", "retired")


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint(f"state IN {STATES}", name="artifacts_state"),
        Index("artifacts_one_per_app", "runtime_id", "name", unique=True),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    runtime_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rrotors.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)  # the program's name on that rrotor
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)  # the rrotor's version number, the one reviewed
    commit_sha: Mapped[str] = mapped_column(Text)
    roles: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    state: Mapped[str] = mapped_column(Text, server_default="draft")
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)  # a rejection's
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
