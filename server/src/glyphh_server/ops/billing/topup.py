"""A top-up of an org's prepaid balance that Stripe says was paid. Nothing sells a top-up any more (the hosted models
were retired on 2026-11-18), but a Checkout started before then can still be paid after (a bank payment takes
days), and money taken is recorded: the amount is an entry in llm_ledger and added to the balance in llm_balances in
the same transaction, once for its Checkout session however often Stripe sends the event. A balance above zero is
owed back to the customer."""

import logging
import uuid
from typing import Any

from sqlalchemy import func, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import LlmBalance, LlmLedger
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.billing")

MICROS_PER_CENT: int = 10_000
KIND: str = "llm_topup"  # the session's metadata kind
PAID_EVENTS: frozenset[str] = frozenset({"checkout.session.completed", "checkout.session.async_payment_succeeded"})


def paid(obj: dict[str, Any]) -> bool:
    """A top-up's session, paid in dollars."""
    ours = (obj.get("metadata") or {}).get("kind") == KIND
    return ours and obj.get("payment_status") == "paid" and obj.get("currency") == "usd"


async def credited(conn: AsyncConnection, org_id: uuid.UUID | None, obj: dict[str, Any]) -> bool:
    """A paid top-up's amount added to the org's balance, once for its session; answers whether it was now."""
    if org_id is None or not paid(obj):
        log.info("checkout payment not credited", extra=fields(session=obj.get("id"), status=obj.get("payment_status")))
        return False
    micros = int(obj["amount_total"]) * MICROS_PER_CENT
    entry = {"org_id": org_id, "kind": "topup", "amount_micros": micros, "stripe_ref": str(obj["id"])}
    made = upsert(LlmLedger).values(**entry).on_conflict_do_nothing().returning(LlmLedger.id)
    if (await conn.execute(made)).first() is None:
        return False
    await conn.execute(upsert(LlmBalance).values(org_id=org_id).on_conflict_do_nothing())
    more = {"micros": LlmBalance.micros + micros, "updated_at": func.now()}
    await conn.execute(update(LlmBalance).where(LlmBalance.org_id == org_id).values(**more))
    log.warning("top-up paid after the wind-down: owed back", extra=fields(org=str(org_id), session=obj.get("id")))
    return True
