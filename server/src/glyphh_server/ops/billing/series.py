"""The org's use day by day, for the platform's Usage charts (GET /v1/billing/series): each UTC day's Ada Cloud reads
(decides among them) and what the balance was charged past the plan's tokens. The tokens by day and model are
/v1/llm/usage's. Precedents have no history: a model holds only its count now. Ada's reads are the database's, which
the minute tick fills from Redis, so today's may lag a minute."""

import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.llm.ledger import MICROS_PER_CENT
from glyphh_server.models import AdaModelDay, LlmUsageDay


class SeriesDay(BaseModel):
    day: date
    reads: int = Field(description="Ada Cloud reads of every kind")
    decides: int = Field(description="Of them, decides")
    charged_cents: float = Field(description="Charged to the balance past the plan's tokens, in cents (fractional)")
    charged_micros: int


class Series(BaseModel):
    days: list[SeriesDay] = Field(description="Oldest first, one a day, today's last")


async def _counts(conn: AsyncConnection, query: Any) -> dict[date, int]:
    return {day: int(n or 0) for day, n in (await conn.execute(query)).all()}


async def _reads(conn: AsyncConnection, org_id: uuid.UUID, since: date, metric: str) -> dict[date, int]:
    found = select(AdaModelDay.day, func.sum(AdaModelDay.n)).where(
        AdaModelDay.org_id == org_id, AdaModelDay.day >= since, AdaModelDay.metric.like(metric)
    )
    return await _counts(conn, found.group_by(AdaModelDay.day))


async def _charged(conn: AsyncConnection, org_id: uuid.UUID, since: date) -> dict[date, int]:
    found = select(LlmUsageDay.day, func.sum(LlmUsageDay.charged_micros)).where(
        LlmUsageDay.org_id == org_id, LlmUsageDay.day >= since
    )
    return await _counts(conn, found.group_by(LlmUsageDay.day))


async def series(conn: AsyncConnection, org_id: uuid.UUID, n: int) -> Series:
    """The last n days, today's included."""
    today = datetime.now(UTC).date()
    since = today - timedelta(days=n - 1)
    reads, decides = await _reads(conn, org_id, since, "read:%"), await _reads(conn, org_id, since, "read:decide")
    charged = await _charged(conn, org_id, since)
    days = []
    for i in range(n):
        day = since + timedelta(days=i)
        micros = charged.get(day, 0)
        days.append(
            SeriesDay(
                day=day,
                reads=reads.get(day, 0),
                decides=decides.get(day, 0),
                charged_cents=micros / MICROS_PER_CENT,
                charged_micros=micros,
            )
        )
    return Series(days=days)
