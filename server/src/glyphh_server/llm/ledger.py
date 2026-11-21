"""The org's overage balance (docs/specs/tokens.md), in microdollars: every movement an entry in llm_ledger and the
sum kept in llm_balances in the same transaction. Money in (a top-up, a staff grant) is credited once: a top-up by its
Stripe Checkout session, so a webhook sent again changes nothing. Charges for tokens past the allowance are added to
one entry a model a UTC day (meter.py)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Row, func, select, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import LlmBalance, LlmLedger

MICROS_PER_CENT: int = 10_000


def period(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m")


async def held(conn: AsyncConnection, org_id: uuid.UUID, lock: bool = False) -> Row:
    """The org's balance row, made at 0 the first time; `lock`: held to the transaction's end."""
    await conn.execute(upsert(LlmBalance).values(org_id=org_id).on_conflict_do_nothing())
    found = select(LlmBalance.micros, LlmBalance.period, LlmBalance.tokens).where(LlmBalance.org_id == org_id)
    return (await conn.execute(found.with_for_update() if lock else found)).one()


async def move(conn: AsyncConnection, org_id: uuid.UUID, micros: int) -> None:
    await held(conn, org_id)
    more = {"micros": LlmBalance.micros + micros, "updated_at": func.now()}
    await conn.execute(update(LlmBalance).where(LlmBalance.org_id == org_id).values(**more))


async def credit(
    conn: AsyncConnection,
    org_id: uuid.UUID,
    kind: str,
    micros: int,
    stripe_ref: str | None = None,
    note: str | None = None,
) -> bool:
    """Money in (or out, a refund's negative): an entry and the balance moved; False when an entry for this Stripe
    reference is there already (nothing moved)."""
    values = {"org_id": org_id, "kind": kind, "amount_micros": micros, "stripe_ref": stripe_ref, "note": note}
    made = upsert(LlmLedger).values(**values).on_conflict_do_nothing().returning(LlmLedger.id)
    if (await conn.execute(made)).first() is None:
        return False
    await move(conn, org_id, micros)
    return True


async def charge(conn: AsyncConnection, org_id: uuid.UUID, model: str, day: str, micros: int) -> None:
    """A request's charge added to its model's entry for the day (made at the day's first), on a locked balance."""
    values = {"org_id": org_id, "kind": "charge", "amount_micros": -micros, "model": model, "period": day}
    made = upsert(LlmLedger).values(**values)
    more = {"amount_micros": LlmLedger.amount_micros - micros, "at": func.now()}
    keys = [LlmLedger.org_id, LlmLedger.model, LlmLedger.period]
    await conn.execute(
        made.on_conflict_do_update(index_elements=keys, index_where=LlmLedger.kind == "charge", set_=more)
    )
    await move(conn, org_id, -micros)
