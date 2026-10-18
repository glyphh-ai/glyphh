from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from glyphh_server.models.base import Base

RATE_ITEMS: tuple[str, ...] = ("small", "medium", "large", "volume")


class FlyRate(Base):
    """What Fly charges Glyphh for one item in one region, a 30-day month's worth: a machine of each size while it is
    started, and a GB of volume always. The rate in force is the newest whose effective_from has come; a new rate is
    a new row, never a change to one. source says where it was read."""

    __tablename__ = "fly_rates"
    __table_args__ = (
        CheckConstraint(f"item IN {RATE_ITEMS}", name="fly_rates_item"),
        CheckConstraint("usd_per_30_days >= 0", name="fly_rates_rate"),
    )

    item: Mapped[str] = mapped_column(Text, primary_key=True)
    region: Mapped[str] = mapped_column(Text, primary_key=True)
    usd_per_30_days: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    effective_from: Mapped[date] = mapped_column(Date, primary_key=True)
    source: Mapped[str] = mapped_column(Text)
