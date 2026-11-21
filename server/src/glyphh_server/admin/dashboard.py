"""The staff view's landing numbers: totals, and each of the last `days` days (UTC): people and orgs signed up, orgs
that read Ada and their reads (ada_model_days, the tick's), models made (admin/adascan.py) and paid conversions (an
org's first payment, orgs.first_paid_at); with revenue and the plan mix (admin/money.py)."""

from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada.requests import period
from glyphh_server.admin import adascan
from glyphh_server.admin.money import Money, money
from glyphh_server.models import AdaModelDay, AdaUsage, Org, User

READ: str = "read:%"


class Day(BaseModel):
    day: date
    new_users: int = 0
    new_orgs: int = 0
    active_orgs: int = Field(0, description="Orgs that read Ada that day")
    reads: int = 0
    models_created: int = 0
    conversions: int = Field(0, description="Orgs that paid for the first time that day")


class Totals(BaseModel):
    users: int
    orgs: int
    suspended_orgs: int
    active_orgs: int = Field(description="Orgs that read Ada in the period")
    reads_month: int = Field(description="Ada reads this calendar month, as the tick last added them")
    models: int = Field(description="Live Ada models")
    precedents: int = Field(description="Precedents their active stores hold")


class Dashboard(BaseModel):
    days: int
    since: date
    totals: Totals
    series: list[Day]
    money: Money


def _by_day(rows: object) -> dict[date, int]:
    return {d: int(n) for d, n in rows}  # type: ignore[attr-defined]


async def _counted(conn: AsyncConnection, column: object, since: date) -> dict[date, int]:
    day = cast(column, Date)
    return _by_day(await conn.execute(select(day, func.count()).where(day >= since).group_by(day)))


async def _reads(conn: AsyncConnection, since: date) -> tuple[dict[date, int], dict[date, int], int]:
    """Each day's reads and orgs that read; and the orgs that read in the whole period."""
    read = AdaModelDay.metric.like(READ), AdaModelDay.day >= since
    rows = list(
        await conn.execute(
            select(AdaModelDay.day, func.sum(AdaModelDay.n), func.count(AdaModelDay.org_id.distinct()))
            .where(*read)
            .group_by(AdaModelDay.day)
        )
    )
    active = (await conn.execute(select(func.count(AdaModelDay.org_id.distinct())).where(*read))).scalar_one()
    return {r[0]: int(r[1]) for r in rows}, {r[0]: int(r[2]) for r in rows}, int(active)


async def _totals(conn: AsyncConnection, active: int, found: list[adascan.OrgAda]) -> Totals:
    orgs = select(func.count(), func.count().filter(Org.suspended_at.is_not(None))).select_from(Org)
    org_count, suspended = (await conn.execute(orgs)).one()
    month = select(func.coalesce(func.sum(AdaUsage.requests), 0)).where(AdaUsage.period == period())
    return Totals(
        users=(await conn.execute(select(func.count()).select_from(User))).scalar_one(),
        orgs=org_count,
        suspended_orgs=suspended,
        active_orgs=active,
        reads_month=int((await conn.execute(month)).scalar_one()),
        models=sum(len(o.live) for o in found),
        precedents=sum(o.precedents for o in found),
    )


async def dashboard(conn: AsyncConnection, redis: Redis, days: int, today: date | None = None) -> Dashboard:
    today = today or datetime.now(UTC).date()
    since = today - timedelta(days=days - 1)
    found = await adascan.scan(conn, redis)
    users, orgs = await _counted(conn, User.created_at, since), await _counted(conn, Org.created_at, since)
    paid = await _counted(conn, Org.first_paid_at, since)
    reads, readers, active = await _reads(conn, since)
    made: dict[date, int] = {}
    for model in (m for o in found for m in o.models):
        made[model.created_at.date()] = made.get(model.created_at.date(), 0) + 1
    series = [
        Day(
            day=d,
            new_users=users.get(d, 0),
            new_orgs=orgs.get(d, 0),
            active_orgs=readers.get(d, 0),
            reads=reads.get(d, 0),
            models_created=made.get(d, 0),
            conversions=paid.get(d, 0),
        )
        for d in (since + timedelta(days=i) for i in range(days))
    ]
    totals = await _totals(conn, active, found)
    return Dashboard(days=days, since=since, totals=totals, series=series, money=await money(conn))
