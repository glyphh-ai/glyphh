"""A hosted-model request's plan checks and its accounting (docs/specs/tokens.md). Before it: the org's calls a second
(a token bucket in Redis, as Ada's, its own key; 429 E_RATE), then it is let in while the month's allowance has tokens
left or the overage balance is above 0 (else 402 E_BALANCE, saying how to add funds). After its reply, in one
transaction on the org's locked balance: its tokens (input + output, x the model's weight) drawn from the allowance,
the part past it charged at the model's rates, rounded up to the microdollar (a request crossing the allowance's edge
is split), its model's day counted. A request may take the balance a little below 0: it is charged after its reply,
as Anthropic does."""

import math
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.api.meter import BUCKET
from glyphh_ada.errors import RateLimited
from glyphh_server.config import Settings
from glyphh_server.db import tenancy
from glyphh_server.errors import NoBalance
from glyphh_server.llm import ledger
from glyphh_server.llm.registry import Model
from glyphh_server.models import LlmBalance, LlmUsageDay
from glyphh_server.ops.plans import org_version


@dataclass(frozen=True)
class Admitted:
    org_id: uuid.UUID
    plan: str
    allowance: int | None  # the plan's tokens a month; None: by contract, never charged


def used_in(row: object, month: str) -> int:
    """The allowance the balance row says was used this month (0 once the month has turned)."""
    return int(row.tokens) if row.period == month else 0  # type: ignore[attr-defined]


async def rate(redis: Redis, org_id: uuid.UUID, rps: int | None) -> None:
    if rps is None:
        return
    taken, wait = await redis.eval(BUCKET, 1, f"llm:rate:{org_id}", rps)  # type: ignore[misc]
    if not taken:
        after = max(1, math.ceil(wait / 1000))
        message = f"Your plan allows {rps} calls a second: try again in {after} second{'s' * (after != 1)}."
        raise RateLimited(message, after, reason="rate", max=rps)


async def admit(engine: AsyncEngine, redis: Redis, settings: Settings, org_id: uuid.UUID) -> Admitted:
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        plan = await org_version(conn, org_id)
        row = await ledger.held(conn, org_id)
    await rate(redis, org_id, plan.cloud_rps)
    used, most = used_in(row, ledger.period()), plan.llm_tokens
    if most is not None and used >= most and row.micros <= 0:
        message = (
            f"Your {plan.name} plan's {most:,} tokens this month are used and your balance is "
            f"${row.micros / 1_000_000:,.2f}: add funds on Billing to go on."
        )
        topup = f"{settings.platform_base}/settings/billing"
        balance_cents = row.micros / ledger.MICROS_PER_CENT
        raise NoBalance(message, reason="tokens", used=used, max=most, balance_cents=balance_cents, topup=topup)
    return Admitted(org_id, plan.name, most)


def split(weighed: int, used: int, most: int | None) -> float:
    """The share of a request's weighed tokens past the allowance: 0 within it, 1 wholly past it."""
    if most is None or weighed == 0:
        return 0.0
    return min(weighed, max(0, used + weighed - most)) / weighed


async def record(engine: AsyncEngine, who: Admitted, model: Model, input_tokens: int, output_tokens: int) -> int:
    """The request's tokens drawn from the allowance, the rest charged; answers its charge in microdollars."""
    now = datetime.now(UTC)
    month, day, weighed = ledger.period(now), now.date(), model.weighed(input_tokens, output_tokens)
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        row = await ledger.held(conn, who.org_id, lock=True)
        used = used_in(row, month)
        cost = model.cost_micros(input_tokens, output_tokens, split(weighed, used, who.allowance))
        more = {"period": month, "tokens": used + weighed}
        await conn.execute(update(LlmBalance).where(LlmBalance.org_id == who.org_id).values(**more))
        if cost:
            await ledger.charge(conn, who.org_id, model.id, day.isoformat(), cost)
        counts = {"input_tokens": input_tokens, "output_tokens": output_tokens, "requests": 1, "charged_micros": cost}
        made = upsert(LlmUsageDay).values(org_id=who.org_id, model=model.id, day=day, **counts)
        added = {k: getattr(LlmUsageDay, k) + v for k, v in counts.items()}
        keys = [LlmUsageDay.org_id, LlmUsageDay.model, LlmUsageDay.day]
        await conn.execute(made.on_conflict_do_update(index_elements=keys, set_=added))
    return cost
