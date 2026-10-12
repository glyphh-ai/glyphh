import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, guid

ASK_KINDS: tuple[str, ...] = ("permission",)
ANSWERS: tuple[str, ...] = ("allow", "deny")


def _sql(values: tuple[str, ...]) -> str:
    """A list for SQL's IN: a one-item tuple's own text has a trailing comma SQL refuses."""
    return "(" + ", ".join(f"'{v}'" for v in values) + ")"


class NeedsYou(Base):
    """A super power's question to its member, kept until it is answered: which thread, what it wants to use and
    one line of what it wants to do. Answered anywhere, it is closed everywhere. Its link to the run that asked
    arrives with runs."""

    __tablename__ = "needs_you"
    __table_args__ = (
        CheckConstraint(f"kind IN {_sql(ASK_KINDS)}", name="needs_you_kind"),
        CheckConstraint(f"answer IS NULL OR answer IN {_sql(ANSWERS)}", name="needs_you_answer"),
        CheckConstraint("char_length(detail) <= 200", name="needs_you_detail"),
        CheckConstraint("(answer IS NULL) = (answered_at IS NULL)", name="needs_you_answered"),
        Index("needs_you_open", "user_id", "asked_at", postgresql_where=text("answer IS NULL")),
        Index("needs_you_ask", "thread_id", "ask_id", unique=True),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    thread_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"))
    super_power_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("super_powers.id", ondelete="CASCADE"))
    session: Mapped[str] = mapped_column(Text, server_default="")
    ask_id: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, server_default="permission")
    tool: Mapped[str] = mapped_column(Text)
    detail: Mapped[str] = mapped_column(Text, server_default="")
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    answer: Mapped[str | None] = mapped_column(Text)
    answered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
