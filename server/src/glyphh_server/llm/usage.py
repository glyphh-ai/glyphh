"""What an org uses of the Glyphh-hosted models (docs/specs/tokens.md), read on a connection that has entered the org:
the month's tokens against the plan's allowance with each model's part, the overage balance, the days, and the
ledger. Money is given in cents (fractional: a request's charge is microdollars) and in microdollars, exact."""

import uuid
from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada.requests import turns
from glyphh_server.llm import ledger, registry
from glyphh_server.models import LlmBalance, LlmLedger, LlmUsageDay

LOW_MICROS: int = 5_000_000  # a balance under $5 is low (TBD, Chris)


class ModelMonth(BaseModel):
    id: str
    name: str
    input_tokens: int
    output_tokens: int
    requests: int
    charged_cents: float = Field(description="Charged past the allowance this month, in cents (fractional)")
    charged_micros: int = Field(description="The same in microdollars (1 = $0.000001)")


class Tokens(BaseModel):
    month: str = Field(description="The calendar month counted, YYYY-MM, UTC")
    resets_at: str = Field(description="When the allowance starts again, YYYY-MM-DD")
    used: int = Field(description="The allowance used: (input + output) x each model's weight, at most max")
    max: int | None = Field(description="The plan's tokens a month; null = by contract")
    over_used: int = Field(description="Weighed tokens past the allowance, charged to the balance")
    models: list[ModelMonth]


class Balance(BaseModel):
    cents: float = Field(description="The overage balance in cents (fractional; below 0 after a last request)")
    micros: int = Field(description="The same in microdollars, exact")
    low: bool = Field(description="Under $5: time to add funds")


class Day(BaseModel):
    day: date
    model: str
    input_tokens: int
    output_tokens: int
    requests: int
    charged_cents: float
    charged_micros: int


class Days(BaseModel):
    days: list[Day]


class Entry(BaseModel):
    at: datetime
    kind: str = Field(
        description="topup, grant, refund (money in or back) or charge (a model's day past the allowance)"
    )
    amount_cents: float = Field(description="Signed: money in positive, charges negative")
    amount_micros: int
    model: str | None = Field(description="A charge's model; null for any other kind")
    note: str | None = Field(description="A charge's day (YYYY-MM-DD), a grant's note, a top-up's Stripe session")


class Ledger(BaseModel):
    entries: list[Entry]


def cents(micros: int) -> float:
    return micros / ledger.MICROS_PER_CENT


async def _row(conn: AsyncConnection, org_id: uuid.UUID) -> tuple[int, str, int]:
    found = select(LlmBalance.micros, LlmBalance.period, LlmBalance.tokens).where(LlmBalance.org_id == org_id)
    row = (await conn.execute(found)).first()
    return (0, "", 0) if row is None else (int(row.micros), row.period, int(row.tokens))


async def balance(conn: AsyncConnection, org_id: uuid.UUID) -> Balance:
    micros = (await _row(conn, org_id))[0]
    return Balance(cents=cents(micros), micros=micros, low=micros < LOW_MICROS)


def _name(model_id: str) -> str:
    found = registry.find(model_id)
    return model_id if found is None else found.name


async def _models(conn: AsyncConnection, org_id: uuid.UUID, month: str) -> list[ModelMonth]:
    first = date.fromisoformat(f"{month}-01")
    sums = [func.sum(getattr(LlmUsageDay, c)) for c in ("input_tokens", "output_tokens", "requests", "charged_micros")]
    found = select(LlmUsageDay.model, *sums).where(LlmUsageDay.org_id == org_id, LlmUsageDay.day >= first)
    rows = await conn.execute(found.group_by(LlmUsageDay.model).order_by(LlmUsageDay.model))
    return [
        ModelMonth(
            id=m, name=_name(m), input_tokens=i, output_tokens=o, requests=r, charged_cents=cents(c), charged_micros=c
        )
        for m, i, o, r, c in rows
    ]


async def tokens(conn: AsyncConnection, org_id: uuid.UUID, most: int | None) -> Tokens:
    month = ledger.period()
    _, held_period, held_tokens = await _row(conn, org_id)
    total = held_tokens if held_period == month else 0
    used = total if most is None else min(total, most)
    models = await _models(conn, org_id, month)
    return Tokens(month=month, resets_at=turns(month), used=used, max=most, over_used=total - used, models=models)


async def days(conn: AsyncConnection, org_id: uuid.UUID, n: int) -> Days:
    since = datetime.now(UTC).date() - timedelta(days=n - 1)
    found = select(LlmUsageDay).where(LlmUsageDay.org_id == org_id, LlmUsageDay.day >= since)
    rows = await conn.execute(found.order_by(LlmUsageDay.day, LlmUsageDay.model))
    return Days(
        days=[
            Day(
                day=r.day,
                model=r.model,
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                requests=r.requests,
                charged_cents=cents(r.charged_micros),
                charged_micros=r.charged_micros,
            )
            for r in rows
        ]
    )


async def entries(conn: AsyncConnection, org_id: uuid.UUID, limit: int) -> Ledger:
    found = select(LlmLedger).where(LlmLedger.org_id == org_id).order_by(LlmLedger.at.desc(), LlmLedger.id)
    rows = await conn.execute(found.limit(limit))
    return Ledger(
        entries=[
            Entry(
                at=r.at,
                kind=r.kind,
                amount_cents=cents(r.amount_micros),
                amount_micros=r.amount_micros,
                model=r.model,
                note=r.note or r.period or r.stripe_ref,
            )
            for r in rows
        ]
    )
