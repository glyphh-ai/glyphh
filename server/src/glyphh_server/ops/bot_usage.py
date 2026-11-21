"""Each bot's month, for the org's usage: its runs, its tokens and what they were charged (the hosted models' meter:
the plan's allowance first, then the balance; docs/specs/bots.md). Read on a connection that has entered the org."""

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.llm import ledger
from glyphh_server.models import Bot, BotRun


class BotMonth(BaseModel):
    slug: str
    name: str
    runs: int = Field(description="Runs started this calendar month, UTC")
    input_tokens: int
    output_tokens: int
    charged_cents: float = Field(description="Its tokens' charge this month, cents (fractional)")
    charged_micros: int = Field(description="The same in microdollars, exact")


def month_start(month: str) -> datetime:
    return datetime.fromisoformat(f"{month}-01").replace(tzinfo=UTC)


async def bots_month(conn: AsyncConnection, org_id: uuid.UUID) -> list[BotMonth]:
    """The org's bots that ran this month, the costliest first."""
    sums = [func.sum(getattr(BotRun, c)) for c in ("input_tokens", "output_tokens", "cost_micros")]
    since = month_start(ledger.period())
    found = (
        select(Bot.slug, Bot.name, func.count(BotRun.id), *sums)
        .join(BotRun, BotRun.bot_id == Bot.id)
        .where(Bot.org_id == org_id, BotRun.created_at >= since)
        .group_by(Bot.slug, Bot.name)
        .order_by(func.sum(BotRun.cost_micros).desc(), Bot.slug)
    )
    return [
        BotMonth(
            slug=slug,
            name=name,
            runs=runs,
            input_tokens=i,
            output_tokens=o,
            charged_cents=c / ledger.MICROS_PER_CENT,
            charged_micros=c,
        )
        for slug, name, runs, i, o, c in await conn.execute(found)
    ]
