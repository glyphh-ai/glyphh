import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class Program(Base):
    """The record of a program: its name and its repo in the person's GitHub. The code, its data and its secrets are
    in the person's repo and rrotor."""

    __tablename__ = "programs"

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(Text)
    repo: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class ProgramVersion(Base):
    """One version of a program: a commit in the program's repo, which is the version's identity, and its manifest.
    The code itself stays in the repo and the runtimes."""

    __tablename__ = "program_versions"
    __table_args__ = (
        UniqueConstraint("program_id", "version", name="program_versions_version"),
        UniqueConstraint("program_id", "commit_sha", name="program_versions_commit"),
    )

    id: Mapped[uuid.UUID] = guid()
    program_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("programs.id", ondelete="CASCADE"), index=True)
    version: Mapped[int]
    commit_sha: Mapped[str] = mapped_column(Text)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = created_at()
