import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base, created_at, guid


class Team(Base):
    """A group of an org's users. An org with teams is team scoped; one without is flat."""

    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("org_id", "name", name="teams_name"),
        UniqueConstraint("id", "org_id", name="teams_id_org"),
        CheckConstraint("rpm_cap > 0 AND tpm_cap > 0", name="teams_caps"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orgs.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(Text)
    rpm_cap: Mapped[int | None]
    tpm_cap: Mapped[int | None]
    created_at: Mapped[datetime] = created_at()


class TeamMember(Base):
    """A user in a team. Both keys carry the org, so a team only ever holds its own org's users."""

    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="team_members_pair"),
        ForeignKeyConstraint(["team_id", "org_id"], ["teams.id", "teams.org_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["user_id", "org_id"], ["users.id", "users.org_id"], ondelete="CASCADE"),
    )

    id: Mapped[uuid.UUID] = guid()
    org_id: Mapped[uuid.UUID] = mapped_column(index=True)
    team_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    created_at: Mapped[datetime] = created_at()
