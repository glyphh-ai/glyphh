"""The staff view's landing numbers: totals, and each of the last `days` days (UTC): people and orgs signed up and
paid conversions (an org's first payment, orgs.first_paid_at); with revenue and the plan mix (admin/money.py).

The platform's dashboard still shows the retired products' numbers (Ada's reads, models and precedents, the orgs
that read): those keys are answered 0 until its screen drops them, then they go from here too."""

from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.admin.money import Money, money
from glyphh_server.models import Org, User


class Day(BaseModel):
    day: date
    new_users: int = 0
    new_orgs: int = 0
    conversions: int = Field(0, description="Orgs that paid for the first time that day")
    active_orgs: int = Field(0, description="Retired with the products: always 0")
    reads: int = Field(0, description="Retired with the products: always 0")
    models_created: int = Field(0, description="Retired with the products: always 0")


class Totals(BaseModel):
    users: int
    orgs: int
    suspended_orgs: int
    active_orgs: int = Field(0, description="Retired with the products: always 0")
    reads_month: int = Field(0, description="Retired with the products: always 0")
    models: int = Field(0, description="Retired with the products: always 0")
    precedents: int = Field(0, description="Retired with the products: always 0")


class Dashboard(BaseModel):
    days: int
    since: date
    totals: Totals
    series: list[Day]
    money: Money


async def _counted(conn: AsyncConnection, column: object, since: date) -> dict[date, int]:
    day = cast(column, Date)
    rows = await conn.execute(select(day, func.count()).where(day >= since).group_by(day))
    return {d: int(n) for d, n in rows}


async def _totals(conn: AsyncConnection) -> Totals:
    orgs = select(func.count(), func.count().filter(Org.suspended_at.is_not(None))).select_from(Org)
    org_count, suspended = (await conn.execute(orgs)).one()
    users = (await conn.execute(select(func.count()).select_from(User))).scalar_one()
    return Totals(users=users, orgs=org_count, suspended_orgs=suspended)


async def dashboard(conn: AsyncConnection, days: int, today: date | None = None) -> Dashboard:
    today = today or datetime.now(UTC).date()
    since = today - timedelta(days=days - 1)
    users, orgs = await _counted(conn, User.created_at, since), await _counted(conn, Org.created_at, since)
    paid = await _counted(conn, Org.first_paid_at, since)
    series = [
        Day(day=d, new_users=users.get(d, 0), new_orgs=orgs.get(d, 0), conversions=paid.get(d, 0))
        for d in (since + timedelta(days=i) for i in range(days))
    ]
    return Dashboard(days=days, since=since, totals=await _totals(conn), series=series, money=await money(conn))
