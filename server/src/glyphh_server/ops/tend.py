"""The server's minute tick, for the staff view: its heartbeat (obs/tick.py), the ops events logged since the last
tick moved to Postgres (obs/events_store.py) and, with a Cloudflare token (GLYPHH_CLOUDFLARE_API_TOKEN), once an
hour, Glyphh's own sites' traffic pulled from Cloudflare's analytics (ops/traffic/pull.py). Nothing of a product is
tended: there are none (retired 2026-11-18).

Every server process runs the tick, and production may run more than one: a tick takes a Postgres advisory lock
(TICK) in a transaction it holds for the tick, and a process that finds it held skips that minute, so no two ticks
ever run at once. Each part runs whatever another does: one failing is logged by name and the rest go on. Ticks one
after another in different processes may both run in the same minute; every part is safe to run again."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.obs import events_store, tick
from glyphh_server.ops.cloudflare import Cloudflare
from glyphh_server.ops.traffic import pull as traffic

log = logging.getLogger("glyphh.tick")

TICK: int = 0x67_6C_74_6B  # one tick at a time across every server process


async def tend(engine: AsyncEngine, redis: Redis, cloudflare: Cloudflare | None = None) -> bool:
    """One tick, if no other process is ticking: answers whether it ran. The lock is the held transaction's, so it
    goes when the transaction ends however it ends (through a connection pooler too), never left behind on a
    connection gone back to a pool."""
    async with engine.begin() as held:
        if not (await held.execute(text("SELECT pg_try_advisory_xact_lock(:lock)"), {"lock": TICK})).scalar_one():
            log.info("tick skipped: another process is ticking")
            return False
        parts: list[tuple[str, Callable[[], Awaitable[Any]]]] = [("heartbeat", lambda: tick.beat(redis))]
        parts.append(("ops events", lambda: events_store.drain(engine, redis)))
        if cloudflare is not None:
            parts.append(("traffic", lambda: traffic.hourly(engine, redis, cloudflare)))
        await _each(parts)
    return True


async def _each(parts: list[tuple[str, Callable[[], Awaitable[Any]]]]) -> None:
    """Every part of the tick in turn, whatever another does: one that fails is logged by its name and the rest run;
    the first failure is raised after."""
    failed: Exception | None = None
    for name, part in parts:
        try:
            await part()
        except Exception as e:
            log.exception("tick part failed: %s", name)
            failed = failed or e
    if failed is not None:
        raise failed
