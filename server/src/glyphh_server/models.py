"""The schema: every table, its keys and its rules (docs/data-model.md draws it). Creates only."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

ROLES: tuple[str, ...] = ("super_admin", "org_admin", "user")


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))


def _created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Base(DeclarativeBase):
    pass


class Org(Base):
    __tablename__ = "orgs"
    __table_args__ = (
        Index("orgs_one_parent", text("(true)"), unique=True, postgresql_where=text("parent_id IS NULL")),
    )

    id: Mapped[uuid.UUID] = _id()
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("orgs.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN {ROLES}", name="users_role"),
        Index("users_email", func.lower(text("email")), unique=True),
    )

    id: Mapped[uuid.UUID] = _id()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="RESTRICT"), index=True)
    role: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text)
    first_name: Mapped[str | None] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created_at()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    access_hash: Mapped[str] = mapped_column(Text, unique=True)
    refresh_hash: Mapped[str] = mapped_column(Text, unique=True)
    access_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    refresh_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created_at()
