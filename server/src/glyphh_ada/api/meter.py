"""A call's plan checks before it is enqueued (docs/specs/ada-cloud.md, section 7), by the API and the connector alike:
the org's calls a second (a token bucket in Redis, refused 429 E_RATE with Retry-After), then a read counted against
its month (requests.py). Past the month, a metered plan (Basic, Pro, Team) goes on, each read over billed; any other
(Free) is refused, 403 E_LIMIT `requests`, saying when it starts again and which plan reads more (from Free, Basic). A
refused read is not counted. A caller with no allowance (an upload's own link) is neither limited nor counted."""

import math
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from glyphh_ada import requests
from glyphh_ada.allowance import Allowance, upgrade_to
from glyphh_ada.api.auth import AdaCaller
from glyphh_ada.errors import RateLimited
from glyphh_server.db import tenancy
from glyphh_server.errors import LimitReached, Unavailable

# A bucket of `rate` tokens, refilled at `rate` a second by Redis's own clock; a call takes one. Answers {1, 0} when
# taken, else {0, ms until one is there}.
BUCKET: str = """
local rate = tonumber(ARGV[1])
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local held = redis.call('HMGET', KEYS[1], 'tokens', 'at')
local tokens = tonumber(held[1]) or rate
local at = tonumber(held[2]) or now
tokens = math.min(rate, tokens + (now - at) * rate / 1000)
local taken, wait = 0, 0
if tokens >= 1 then
  tokens = tokens - 1
  taken = 1
else
  wait = math.ceil((1 - tokens) * 1000 / rate)
end
redis.call('HSET', KEYS[1], 'tokens', tostring(tokens), 'at', now)
redis.call('PEXPIRE', KEYS[1], 60000)
return {taken, wait}
"""


async def _rate(redis: Redis, who: AdaCaller, rps: int) -> None:
    taken, wait = await redis.eval(BUCKET, 1, f"ada:rate:{who.org_id}", rps)  # type: ignore[misc]
    if not taken:
        after = max(1, math.ceil(wait / 1000))
        message = f"Your plan allows {rps} Ada calls a second: try again in {after} second{'s' * (after != 1)}."
        raise RateLimited(message, after, reason="rate", max=rps)


async def _count(state: Any, who: AdaCaller, allowed: Allowance, n: int) -> None:
    month, org, redis = requests.period(), who.org_id, state.redis
    total_key, pending_key = requests.total_key(org, month), requests.pending_key(org, month)
    async with redis.pipeline(transaction=True) as pipe:
        pipe.incrby(total_key, n).expire(total_key, requests.KEPT_SECONDS)
        pipe.incrby(pending_key, n).expire(pending_key, requests.KEPT_SECONDS)
        pipe.sadd(requests.orgs_key(month), str(org)).expire(requests.orgs_key(month), requests.KEPT_SECONDS)
        total = (await pipe.execute())[0]
    if total == n:  # the month's first read here, or Redis lost its count: the database's count under it
        async with state.engine.begin() as conn:
            await tenancy.enter(conn, org)
            kept = await requests.kept(conn, org, month)
        if kept:
            total = await redis.incrby(total_key, kept)
    if allowed.requests is None or allowed.overage or total <= allowed.requests:
        return
    async with redis.pipeline(transaction=True) as pipe:
        await pipe.decrby(total_key, n).decrby(pending_key, n).execute()
    raise await _over(state, allowed, total - n, month)


async def _over(state: Any, allowed: Allowance, used: int, month: str) -> LimitReached:
    async with state.engine.begin() as conn:
        better = await upgrade_to(conn, allowed)
    again = requests.turns(month)
    how = (
        f"Upgrade to {better} (the connector's upgrade tool, or Billing on the platform) to read on now."
        if better
        else "Talk to us at sales@glyphh.ai to read more."
    )
    message = (
        f"Your {allowed.plan} plan's {allowed.requests:,} Ada reads this month are used: they start again on {again}. "
        + how
    )
    detail = {"reason": "requests", "used": used, "max": allowed.requests, "plan": allowed.plan}
    return LimitReached(message, **detail, upgrade=better, resets_at=again)


async def admit(state: Any, who: AdaCaller, op: str, args: dict[str, Any]) -> None:
    """The org's plan lets this call through, and a read is counted; else refused before anything is enqueued."""
    allowed = who.allowance
    if allowed is None:
        return
    try:
        if allowed.rps is not None:
            await _rate(state.redis, who, allowed.rps)
        n = requests.reads(op, args)
        if n:
            await _count(state, who, allowed, n)
    except RedisError:
        raise Unavailable("Ada is unreachable for a moment: try again.", reason="queue") from None
