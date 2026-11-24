import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.api import HostRouter
from glyphh_ada.api import make_app as make_ada
from glyphh_server.api import (
    admin,
    attribution,
    billing,
    connector,
    device,
    device_pages,
    errors,
    health,
    llm,
    mcp,
    me,
    oauth,
    oauth_meta,
    oauth_pages,
    org,
    plans,
)
from glyphh_server.api.consent_cors import ConsentCorsMiddleware
from glyphh_server.api.trace import TraceMiddleware
from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.db.signals import make_redis
from glyphh_server.obs import events, metrics
from glyphh_server.obs.logs import configure
from glyphh_server.ops import tend
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.cloudflare import Cloudflare
from glyphh_server.ops.github_traffic import GitHub

ROUTERS = (
    health,
    device,
    device_pages,
    me,
    org,
    plans,
    billing,
    llm,
    oauth_meta,
    oauth,
    oauth_pages,
    connector,
    mcp,
    attribution,
    admin,
)


IDLE_EVERY: float = 60.0


async def tend_forever(
    engine: AsyncEngine,
    redis: Redis,
    cfg: Settings,
    stripe: StripeClient | None,
    cloudflare: Cloudflare | None = None,
    github: GitHub | None = None,
) -> None:
    """Every minute, the server's tick (ops/tend.py); a failure is logged and the next minute comes."""
    while True:
        await asyncio.sleep(IDLE_EVERY)
        try:
            await tend.tend(engine, redis, cfg, stripe, cloudflare, github)
        except Exception:
            logging.getLogger("glyphh.runtime").exception("tick failed")


def _tending(app: FastAPI, cfg: Settings, engine: AsyncEngine) -> asyncio.Task[None]:
    """The minute tick, always; with billing set up, Stripe (Ada Cloud's meter); with a Cloudflare token, the hourly
    traffic pull; with a GitHub traffic token, the hourly GitHub traffic pull."""
    meter = cfg.stripe_secret_key and StripeClient(app.state.http, cfg.stripe_secret_key, cfg.stripe_meter_ada)
    cloudflare = Cloudflare(app.state.http, cfg.cloudflare_api_token) if cfg.cloudflare_api_token else None
    github = GitHub(app.state.http, cfg.github_traffic_token) if cfg.github_traffic_token else None
    return asyncio.create_task(tend_forever(engine, app.state.redis, cfg, meter or None, cloudflare, github))


def _share_http(app: FastAPI, http: httpx.AsyncClient) -> None:
    """The server's HTTP client, the Ada app's too while it is on (the hosted models' inference, api/inference.py)."""
    app.state.http = http
    if app.state.ada is not None:
        app.state.ada.http = http


def create_app(settings: Settings | None = None, http: httpx.AsyncClient | None = None) -> FastAPI:
    cfg: Settings = settings or get_settings()
    configure(cfg.log_level)
    if len(cfg.secret_key) < 32:
        raise RuntimeError("GLYPHH_SECRET_KEY must be set, 32 characters or more: it signs every sign-in step.")
    engine = make_engine(cfg.database_url)
    redis = make_redis(cfg.redis_url)
    ada = make_ada(cfg, engine) if cfg.ada_cloud else None  # off, nothing of Ada Cloud is reachable

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        _share_http(app, http or httpx.AsyncClient(timeout=10))
        idle = _tending(app, cfg, engine)
        flushing = asyncio.create_task(metrics.flush_forever(app.state.metrics, redis))
        yield
        await metrics.stop(flushing, app.state.metrics, redis)
        idle.cancel()
        with suppress(asyncio.CancelledError):
            await idle
        await app.state.http.aclose()
        await redis.aclose()
        if ada is not None:
            await ada.state.redis.aclose()
        await engine.dispose()

    app = FastAPI(title="Glyphh", version=cfg.version, lifespan=lifespan)
    app.state.settings = cfg
    app.state.engine = engine
    app.state.redis = redis
    app.state.ada = None if ada is None else ada.state  # the connector's Ada tools call the workers through it
    errors.install(app)
    for module in ROUTERS:
        app.include_router(module.router)
    _wrap(app, cfg, ada)
    return app


def _wrap(app: FastAPI, cfg: Settings, ada: FastAPI | None) -> None:
    """The outer layers, innermost first: Ada Cloud's host (when on), CORS for the platform's read of a consent, the
    request metrics (every host's), then the trace. Warnings and errors are kept for staff as ops events
    (obs/events.py)."""
    app.state.metrics = metrics.Recorder()  # every request's route, status and time (obs/metrics.py)
    events.install(cfg.redis_url)
    if ada is not None:
        app.add_middleware(HostRouter, ada=ada, hosts=cfg.ada_host_set)
    app.add_middleware(ConsentCorsMiddleware, platform_origin=cfg.platform_base)
    app.add_middleware(metrics.MetricsMiddleware, recorder=app.state.metrics)
    app.add_middleware(TraceMiddleware)
