"""Fly's rates for the hosted machines, as read from Fly's pricing page (region iad, a 30-day month). A rate Fly
changes is a new row with its own effective_from, added here; a row already there is never changed."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import FlyRate

SOURCE: str = "https://docs.fly.io/about/pricing"


@dataclass(frozen=True, slots=True)
class RateSeed:
    item: str
    region: str
    usd_per_30_days: Decimal
    effective_from: date
    source: str = SOURCE


# Read 2026-10-18. medium: shared-cpu-2x 2 GB ($13.39) and 2 GB more at $6.00; large: performance-2x 4 GB ($66.00) and
# 4 GB more at $6.00 (models/rrotor.py, SIZES).
READ: date = date(2026, 10, 18)
RATES: tuple[RateSeed, ...] = (
    RateSeed("small", "iad", Decimal("6.70"), READ),
    RateSeed("medium", "iad", Decimal("25.39"), READ),
    RateSeed("large", "iad", Decimal("90.00"), READ),
    RateSeed("volume", "iad", Decimal("0.15"), READ),
)


async def seed_rates(conn: AsyncConnection) -> None:
    for rate in RATES:
        values = {
            "item": rate.item,
            "region": rate.region,
            "usd_per_30_days": rate.usd_per_30_days,
            "effective_from": rate.effective_from,
            "source": rate.source,
        }
        await conn.execute(upsert(FlyRate).values(**values).on_conflict_do_nothing())
