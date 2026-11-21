"""The org's use day by day, for the platform's Usage charts (GET /v1/billing/series): each UTC day's Ada Cloud reads
(decides among them), bot runs, what the balance was charged past the plan's tokens, and the connections the org
held at the day's end. The tokens by day and model are /v1/llm/usage's. Precedents have no history: a model holds
only its count now. Ada's reads are the database's, which the minute tick fills from Redis, so today's may lag a
minute. A deleted connection leaves no row, so the connections are those the org holds now, counted from when each
was made."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.llm.ledger import MICROS_PER_CENT
from glyphh_server.models import AdaModelDay, BotRun, Connection, LlmUsageDay


class SeriesDay(BaseModel):
    day: date
    reads: int = Field(description="Ada Cloud reads of every kind")
    decides: int = Field(description="Of them, decides")
    bot_runs: int
    charged_cents: float = Field(description="Charged to the balance past the plan's tokens, in cents (fractional)")
    charged_micros: int
    connections: int = Field(description="The connections held at the day's end")
    connections_added: int


class Series(BaseModel):
    days: list[SeriesDay] = Field(description="Oldest first, one a day, today's last")


def _utc_day(column: Any) -> Any:
    return cast(func.timezone("UTC", column), Date)


async def _counts(conn: AsyncConnection, query: Any) -> dict[date, int]:
    return {day: int(n or 0) for day, n in (await conn.execute(query)).all()}


async def _reads(conn: AsyncConnection, org_id: uuid.UUID, since: date, metric: str) -> dict[date, int]:
    found = select(AdaModelDay.day, func.sum(AdaModelDay.n)).where(
        AdaModelDay.org_id == org_id, AdaModelDay.day >= since, AdaModelDay.metric.like(metric)
    )
    return await _counts(conn, found.group_by(AdaModelDay.day))


async def _runs(conn: AsyncConnection, org_id: uuid.UUID, since: date) -> dict[date, int]:
    day = _utc_day(BotRun.created_at)
    return await _counts(conn, select(day, func.count()).where(BotRun.org_id == org_id, day >= since).group_by(day))


async def _charged(conn: AsyncConnection, org_id: uuid.UUID, since: date) -> dict[date, int]:
    found = select(LlmUsageDay.day, func.sum(LlmUsageDay.charged_micros)).where(
        LlmUsageDay.org_id == org_id, LlmUsageDay.day >= since
    )
    return await _counts(conn, found.group_by(LlmUsageDay.day))


async def _connections(conn: AsyncConnection, org_id: uuid.UUID, since: date) -> tuple[int, dict[date, int]]:
    """Those made before the window, and those made each day in it."""
    day = _utc_day(Connection.created_at)
    mine = Connection.org_id == org_id
    before = (await conn.execute(select(func.count()).where(mine, day < since))).scalar_one()
    added = await _counts(conn, select(day, func.count()).where(mine, day >= since).group_by(day))
    return int(before), added


async def series(conn: AsyncConnection, org_id: uuid.UUID, n: int) -> Series:
    """The last n days, today's included."""
    today = datetime.now(UTC).date()
    since = today - timedelta(days=n - 1)
    reads, decides = await _reads(conn, org_id, since, "read:%"), await _reads(conn, org_id, since, "read:decide")
    runs, charged = await _runs(conn, org_id, since), await _charged(conn, org_id, since)
    held, added = await _connections(conn, org_id, since)
    days = []
    for i in range(n):
        day = since + timedelta(days=i)
        held += added.get(day, 0)
        micros = charged.get(day, 0)
        days.append(
            SeriesDay(
                day=day,
                reads=reads.get(day, 0),
                decides=decides.get(day, 0),
                bot_runs=runs.get(day, 0),
                charged_cents=micros / MICROS_PER_CENT,
                charged_micros=micros,
                connections=held,
                connections_added=added.get(day, 0),
            )
        )
    return Series(days=days)
