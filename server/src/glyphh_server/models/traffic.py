"""Glyphh's own sites' traffic, as Cloudflare's analytics give it (ops/traffic.py), for the staff view: each zone the
token sees and what its plan let the last pull have, each day's numbers by zone and host, and each day's tops
(countries, pages, referrers). Pulled by the tick each hour, so a page load never calls Cloudflare. Staff only."""

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
