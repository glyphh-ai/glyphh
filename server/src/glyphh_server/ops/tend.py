"""The server's minute tick, with or without hosting on: with hosting on (GLYPHH_HOSTING), every hosted machine metered
at Fly's rates up to now, its online seconds this month tallied (ops/metering.py); always, the keys that expired
taken off their runtimes, the Enterprise grants past their date ended (their hosting due reported first) and server-
side logging past its retention purged (ops/telemetry/retention.py); with hosting on, the idle machines and those
held past their plan stopped; and the hosting due reported to Stripe's meter (ops/billing/meter.py). With Ada Cloud on
(GLYPHH_ADA_CLOUD), its reads counted in Redis added to ada_usage (glyphh_ada/requests.py) and its models' days to
ada_model_days (glyphh_ada/days.py), and the reads past a metered plan's month reported to Stripe's ada_requests meter
(ops/billing/ada_meter.py). With a Cloudflare token (GLYPHH_CLOUDFLARE_API_TOKEN), once an hour, Glyphh's own sites'
traffic pulled from Cloudflare's analytics (ops/traffic/pull.py); with a GitHub token (GLYPHH_GITHUB_TRAFFIC_TOKEN),
once an hour, its public repositories' views and clones pulled from GitHub (ops/traffic/github.py). Always first, its
heartbeat (obs/tick.py) and the ops events logged since the last tick moved to Postgres (obs/events_store.py), for
the staff view.

Every server process runs the tick, and production runs more than one: a tick takes a Postgres advisory lock (TICK)
in a transaction it holds for the tick, and a process that finds it held skips that minute, so no two ticks ever run
at once. Each part runs whatever another does: one failing is logged by name and the rest go on. Ticks one after
another in different processes may both run in the same minute; every part is safe to run again: the meter counts
the time since each machine was last metered, never a fixed step."""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import days
from glyphh_ada.requests import flush
from glyphh_server.config import Settings
from glyphh_server.obs import events_store, tick
from glyphh_server.ops.billing import ada_meter
from glyphh_server.ops.billing.meter import report
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.cloudflare import Cloudflare
from glyphh_server.ops.enterprise import expire
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.github_traffic import GitHub
from glyphh_server.ops.held import hold
from glyphh_server.ops.idle import stop_idle
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.metering import meter
from glyphh_server.ops.runtime_keys import push_expired
from glyphh_server.ops.telemetry.retention import purge
from glyphh_server.ops.traffic import github as github_traffic
from glyphh_server.ops.traffic import pull as traffic

log = logging.getLogger("glyphh.runtime")

TICK: int = 0x67_6C_74_6B  # one tick at a time across every server process


async def tally(engine: AsyncEngine, region: str, now: datetime | None = None) -> None:
    """Every hosted machine metered and its month tallied up to `now`, else the database's clock: one clock for every
    process."""
    async with engine.begin() as conn:  # the connecting role: every org's runtimes
        await meter(conn, now or (await conn.execute(text("SELECT now()"))).scalar_one(), region)


async def tend(
    engine: AsyncEngine,
    hub: Hub,
    settings: Settings,
    step: int,
    fly: Fly | None,
    stripe: StripeClient | None,
    cloudflare: Cloudflare | None = None,
    github: GitHub | None = None,
) -> bool:
    """One tick, if no other process is ticking: answers whether it ran. The lock is the held transaction's, so it
    goes when the transaction ends however it ends (through a connection pooler too), never left behind on a
    connection gone back to a pool."""
    async with engine.begin() as held:
        if not (await held.execute(text("SELECT pg_try_advisory_xact_lock(:lock)"), {"lock": TICK})).scalar_one():
            log.info("tick skipped: another process is ticking")
            return False
        await _tick(engine, hub, settings, step, fly, stripe, cloudflare, github)
    return True


async def _each(parts: list[tuple[str, Callable[[], Awaitable[Any]]]]) -> None:
    """Every part of the tick in turn, whatever another does: one that fails is logged by its name and the rest run
    (Ada's counts reach the database even while the hosting meter fails); the first failure is raised after."""
    failed: Exception | None = None
    for name, part in parts:
        try:
            await part()
        except Exception as e:
            log.exception("tick part failed: %s", name)
            failed = failed or e
    if failed is not None:
        raise failed


async def _tick(
    engine: AsyncEngine,
    hub: Hub,
    settings: Settings,
    step: int,
    fly: Fly | None,
    stripe: StripeClient | None,
    cloudflare: Cloudflare | None,
    github: GitHub | None,
) -> None:
    """With hosting on, the month tallied and metered; the keys that expired since the last tick (with a tick to spare)
    taken off their runtimes, the Enterprise grants past their date ended (with Stripe, their hosting due reported
    first), server-side logging past retention purged; with hosting on and Fly set up, the idle machines stopped and
    those held past their plan stopped; with Stripe, the hosting due reported to its meter. With Ada Cloud on, its
    reads flushed to the database, and with Stripe those past a metered plan's month reported."""
    parts: list[tuple[str, Callable[[], Awaitable[Any]]]] = [("heartbeat", lambda: tick.beat(hub.redis))]
    parts.append(("ops events", lambda: events_store.drain(engine, hub.redis)))
    if settings.hosting:
        parts.append(("tally", lambda: tally(engine, settings.fly_region)))
    parts.append(("expired keys", lambda: push_expired(engine, hub, timedelta(seconds=2 * step))))
    parts.append(("enterprise grants", lambda: expire(engine, stripe)))
    parts.append(("retention", lambda: purge(engine, settings.telemetry_retention_days)))
    if fly is not None:
        parts.append(("idle", lambda: stop_idle(engine, fly, timedelta(minutes=settings.runtime_idle_minutes))))
        parts.append(("held", lambda: _hold(engine, fly)))
    if settings.ada_cloud:
        parts.append(("ada reads", lambda: flush(engine, hub.redis)))
        parts.append(("ada days", lambda: days.flush(engine, hub.redis)))
    if stripe is not None:
        parts.append(("hosting meter", lambda: report(engine, stripe)))
        if settings.ada_cloud:
            parts.append(("ada meter", lambda: ada_meter.report(engine, stripe, settings.stripe_price_ada)))
    if cloudflare is not None:
        parts.append(("traffic", lambda: traffic.hourly(engine, hub.redis, cloudflare)))
    if github is not None:
        listed = github_traffic.repos(settings.github_traffic_repos)
        parts.append(("github traffic", lambda: github_traffic.hourly(engine, hub.redis, github, listed)))
    await _each(parts)


async def _hold(engine: AsyncEngine, fly: Fly) -> None:
    async with engine.begin() as conn:  # the connecting role: every org's
        await hold(conn, fly)
