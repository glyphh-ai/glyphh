"""The template library (docs/specs/templates.md): the templates Glyphh ships, seeded at every start
(ops/templates/library.py), and each person's installs. An install is a person's, never their org's: the tools it
adds are on their own connector and the models it makes are theirs."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class Template(Base):
    __tablename__ = "templates"

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)  # the whole template (ops/templates/library.Body)
    active: Mapped[bool] = mapped_column(server_default="true")  # retired when no longer shipped, never deleted
    sort: Mapped[int] = mapped_column(server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TemplateInstall(Base):
    __tablename__ = "template_installs"
    __table_args__ = (Index("template_installs_one_per_person", "user_id", "slug", unique=True),)

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(ForeignKey("templates.slug", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)  # the template's version when installed
    created_at: Mapped[datetime] = created_at()
