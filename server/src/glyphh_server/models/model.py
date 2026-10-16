import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class Model(Base):
    """The record of a model: its name and its repo in the person's GitHub. The code, its data and its secrets are
    in the person's repo and rrotor."""

    __tablename__ = "models"

    id: Mapped[uuid.UUID] = guid()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(Text)
    repo: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class ModelVersion(Base):
    """One version of a model: a commit in the model's repo, which is the version's identity, and its manifest.
    The code itself stays in the repo and the runtimes."""

    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("model_id", "version", name="model_versions_version"),
        UniqueConstraint("model_id", "commit_sha", name="model_versions_commit"),
    )

    id: Mapped[uuid.UUID] = guid()
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("models.id", ondelete="CASCADE"), index=True)
    version: Mapped[int]
    commit_sha: Mapped[str] = mapped_column(Text)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = created_at()
