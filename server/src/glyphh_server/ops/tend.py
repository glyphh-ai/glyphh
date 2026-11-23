"""The server's minute tick: always, the runtime keys that expired taken off their runtimes and the Enterprise grants
past their date ended. With Ada Cloud on (GLYPHH_ADA_CLOUD), its reads counted in Redis added to ada_usage
(glyphh_ada/requests.py) and its models' days to ada_model_days (glyphh_ada/days.py), and the reads past a metered
plan's month reported to Stripe's ada_requests meter (ops/billing/ada_meter.py). With a Cloudflare token
(GLYPHH_CLOUDFLARE_API_TOKEN), once an hour, Glyphh's own sites' traffic pulled from Cloudflare's analytics
(ops/traffic/pull.py); with a GitHub token (GLYPHH_GITHUB_TRAFFIC_TOKEN), once an hour, its public repositories' views
and clones pulled from GitHub (ops/traffic/github.py). Always first, its heartbeat (obs/tick.py) and the ops events
logged since the last tick moved to Postgres (obs/events_store.py), for the staff view. Given the hosted bots, the
bots and programs whose schedule is due run (ops/bots/due.py, ops/programs/due.py), on the ticking process.

Every server process runs the tick, and production runs more than one: a tick takes a Postgres advisory lock (TICK)
in a transaction it holds for the tick, and a process that finds it held skips that minute, so no two ticks ever run
at once. Each part runs whatever another does: one failing is logged by name and the rest go on. Ticks one after
another in different processes may both run in the same minute; every part is safe to run again."""

import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import days
from glyphh_ada.requests import flush
from glyphh_server.config import Settings
from glyphh_server.obs import events_store, tick
from glyphh_server.ops.billing import ada_meter
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.bots import due
from glyphh_server.ops.bots.service import Bots
from glyphh_server.ops.cloudflare import Cloudflare
from glyphh_server.ops.enterprise import expire
from glyphh_server.ops.github_traffic import GitHub
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.programs import due as program_due
from glyphh_server.ops.runtime_keys import push_expired
from glyphh_server.ops.traffic import github as github_traffic
from glyphh_server.ops.traffic import pull as traffic

log = logging.getLogger("glyphh.runtime")

TICK: int = 0x67_6C_74_6B  # one tick at a time across every server process


async def tend(
    engine: AsyncEngine,
    hub: Hub,
    settings: Settings,
    step: int,
    stripe: StripeClient | None,
    cloudflare: Cloudflare | None = None,
    github: GitHub | None = None,
    bots: Bots | None = None,
) -> bool:
    """One tick, if no other process is ticking: answers whether it ran. The lock is the held transaction's, so it
    goes when the transaction ends however it ends (through a connection pooler too), never left behind on a
    connection gone back to a pool."""
    async with engine.begin() as held:
        if not (await held.execute(text("SELECT pg_try_advisory_xact_lock(:lock)"), {"lock": TICK})).scalar_one():
            log.info("tick skipped: another process is ticking")
            return False
        await _tick(engine, hub, settings, step, stripe, cloudflare, github, bots)
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


async def _tick(
    engine: AsyncEngine,
    hub: Hub,
    settings: Settings,
    step: int,
    stripe: StripeClient | None,
    cloudflare: Cloudflare | None,
    github: GitHub | None,
    bots: Bots | None = None,
) -> None:
    """The keys that expired since the last tick (with a tick to spare) taken off their runtimes, the Enterprise grants
    past their date ended. With Ada Cloud on, its reads flushed to the database, and with Stripe those past a metered
    plan's month reported."""
    parts: list[tuple[str, Callable[[], Awaitable[Any]]]] = [("heartbeat", lambda: tick.beat(hub.redis))]
    parts.append(("ops events", lambda: events_store.drain(engine, hub.redis)))
    parts.append(("expired keys", lambda: push_expired(engine, hub, timedelta(seconds=2 * step))))
    parts.append(("enterprise grants", lambda: expire(engine)))
    if settings.ada_cloud:
        parts.append(("ada reads", lambda: flush(engine, hub.redis)))
        parts.append(("ada days", lambda: days.flush(engine, hub.redis)))
        if stripe is not None:
            parts.append(("ada meter", lambda: ada_meter.report(engine, stripe, settings.stripe_price_ada)))
    if cloudflare is not None:
        parts.append(("traffic", lambda: traffic.hourly(engine, hub.redis, cloudflare)))
    if github is not None:
        listed = github_traffic.repos(settings.github_traffic_repos)
        parts.append(("github traffic", lambda: github_traffic.hourly(engine, hub.redis, github, listed)))
    if bots is not None:
        parts.append(("bot schedules", lambda: due.fire(bots)))
        parts.append(("program schedules", lambda: program_due.fire(bots.programs)))
    await _each(parts)
