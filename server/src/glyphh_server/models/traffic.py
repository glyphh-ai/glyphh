"""Glyphh's own sites' traffic, as Cloudflare's analytics give it (ops/traffic.py), for the staff view: each zone the
token sees and what its plan let the last pull have, each day's numbers by zone and host, and each day's tops
(countries, pages, referrers); and Glyphh's public repositories' views and clones from GitHub (ops/traffic/github.py).
Pulled by the tick each hour, so a page load never calls Cloudflare or GitHub. Staff only."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base


class TrafficZone(Base):
    """A zone (glyphh.ai): its Cloudflare id and plan, when it was last pulled and what that pull could have
    (`available`: each part's state, the window its plan allows and why not, if not)."""

    __tablename__ = "traffic_zones"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    zone_id: Mapped[str] = mapped_column(Text)
    plan: Mapped[str | None] = mapped_column(Text)
    pulled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    available: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


class TrafficDay(Base):
    """One number of one UTC day: the whole zone's (host '') or one hostname's."""

    __tablename__ = "traffic_days"

    zone: Mapped[str] = mapped_column(Text, primary_key=True)
    host: Mapped[str] = mapped_column(Text, primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    metric: Mapped[str] = mapped_column(Text, primary_key=True)
    n: Mapped[int] = mapped_column(BigInteger, server_default="0")


class TrafficTop(Base):
    """One day's count of one country, page or referrer (`kind`), the zone's (host '') or one hostname's."""

    __tablename__ = "traffic_tops"

    zone: Mapped[str] = mapped_column(Text, primary_key=True)
    host: Mapped[str] = mapped_column(Text, primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    n: Mapped[int] = mapped_column(BigInteger, server_default="0")


class GitHubTrafficRepo(Base):
    """A public repository's traffic as the last pull found it (ops/traffic/github.py): GitHub's own totals of the
    last 14 days, views and clones with their unique visitors and cloners."""

    __tablename__ = "github_traffic_repos"

    repo: Mapped[str] = mapped_column(Text, primary_key=True)
    pulled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    views: Mapped[int] = mapped_column(BigInteger, server_default="0")
    view_uniques: Mapped[int] = mapped_column(BigInteger, server_default="0")
    clones: Mapped[int] = mapped_column(BigInteger, server_default="0")
    clone_uniques: Mapped[int] = mapped_column(BigInteger, server_default="0")


class GitHubTrafficDay(Base):
    """One UTC day of a repository's views and clones, kept beyond GitHub's 14 days, replaced while GitHub reports
    it."""

    __tablename__ = "github_traffic_days"

    repo: Mapped[str] = mapped_column(Text, primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    views: Mapped[int] = mapped_column(BigInteger, server_default="0")
    view_uniques: Mapped[int] = mapped_column(BigInteger, server_default="0")
    clones: Mapped[int] = mapped_column(BigInteger, server_default="0")
    clone_uniques: Mapped[int] = mapped_column(BigInteger, server_default="0")


class GitHubTrafficTop(Base):
    """A repository's popular referrer or path (`kind`) as one day's pull found it: GitHub's 14-day totals."""

    __tablename__ = "github_traffic_tops"

    repo: Mapped[str] = mapped_column(Text, primary_key=True)
    pulled_on: Mapped[date] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(Text, primary_key=True)
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    count: Mapped[int] = mapped_column(BigInteger, server_default="0")
    uniques: Mapped[int] = mapped_column(BigInteger, server_default="0")
