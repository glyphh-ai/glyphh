"""Fly's rates, as the hosted machines are billed on them: the rate in force for each item (the newest whose
effective_from has come), per second over a 30-day month; and the rates as people see them, each paid plan's with its
markup in them and the markup never named."""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Unavailable
from glyphh_server.models import FlyRate
from glyphh_server.models.rrotor import SIZES
from glyphh_server.ops.plans import newest_versions

SECONDS_PER_MONTH: int = 2_592_000  # 30 days: Fly's month
VOLUME: str = "volume"
CENT, TINY = Decimal("0.01"), Decimal("1e-10")


@dataclass(frozen=True, slots=True)
class InForce:
    usd: dict[str, Decimal]  # each item's rate, a 30-day month's worth
    effective_from: date
    source: str


async def in_force(conn: AsyncConnection, region: str, on: date) -> InForce | None:
    """The rates in force in a region on a day; None when it has none."""
    newest = (
        select(FlyRate.item, FlyRate.usd_per_30_days, FlyRate.effective_from, FlyRate.source)
        .ext(distinct_on(FlyRate.item))
        .where(FlyRate.region == region, FlyRate.effective_from <= on)
        .order_by(FlyRate.item, FlyRate.effective_from.desc())
    )
    rows = list(await conn.execute(newest))
    if not rows:
        return None
    latest = max(rows, key=lambda r: r.effective_from)
    return InForce({r.item: r.usd_per_30_days for r in rows}, latest.effective_from, latest.source)


class SizeSpec(BaseModel):
    size: str
    cpu_kind: str
    cpus: int
    memory_mb: int
    volume_gb: int = Field(description="Its volume, billed always at the plan's volume_usd_per_gb_month")


class SizeRate(SizeSpec):
    usd_per_month: float = Field(description="While started, a 30-day month; its volume is apart")
    usd_per_second: float


class PlanRates(BaseModel):
    sizes: list[SizeRate]
    volume_usd_per_gb_month: float


class Rates(BaseModel):
    """What people see: each size's machine, and what each self-serve paid plan is billed for it. Never Fly's own
    rates, their source or the markup, from which the markup could be worked out."""

    effective_from: date
    region: str
    sizes: list[SizeSpec] = Field(description="Each size's machine")
    plans: dict[str, PlanRates] = Field(description="What each self-serve paid plan is billed: its rates, all in")


def _sizes(rates: InForce, factor: Decimal) -> list[SizeRate]:
    out = []
    for name, size in SIZES.items():
        month = (rates.usd[name] * factor).quantize(CENT, ROUND_HALF_UP)
        per_second = (month / SECONDS_PER_MONTH).quantize(TINY, ROUND_HALF_UP)
        out.append(SizeRate(size=name, **size.fields(), usd_per_month=float(month), usd_per_second=float(per_second)))
    return out


def _plan(rates: InForce, markup_pct: int) -> PlanRates:
    factor = 1 + Decimal(markup_pct) / 100
    volume = (rates.usd[VOLUME] * factor).quantize(CENT, ROUND_HALF_UP)
    return PlanRates(sizes=_sizes(rates, factor), volume_usd_per_gb_month=float(volume))


async def public_rates(conn: AsyncConnection, region: str, on: date) -> Rates:
    rates = await in_force(conn, region, on)
    if rates is None:
        raise Unavailable("Hosting has no rates in this region yet.", reason="no_rates", region=region)
    plans = {r.name: _plan(rates, r.hosting_markup_pct) for r in await newest_versions(conn) if r.hosting_markup_pct}
    return Rates(
        effective_from=rates.effective_from,
        region=region,
        sizes=[SizeSpec(size=name, **size.fields()) for name, size in SIZES.items()],
        plans=plans,
    )
