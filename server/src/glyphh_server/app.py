import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.api import admin, billing, errors, gone, health, me, oauth, oauth_pages, signin_pages
from glyphh_server.api.consent_cors import ConsentCorsMiddleware
from glyphh_server.api.trace import TraceMiddleware
from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.db.signals import make_redis
from glyphh_server.obs import events, metrics
from glyphh_server.obs.logs import configure
from glyphh_server.ops import tend
from glyphh_server.ops.cloudflare import Cloudflare

# Everything the server still answers; any other address is gone (api/gone.py).
ROUTERS = (health, billing, me, oauth, oauth_pages, signin_pages, admin)

IDLE_EVERY: float = 60.0


async def tend_forever(engine: AsyncEngine, redis: Redis, cloudflare: Cloudflare | None = None) -> None:
    """Every minute, the server's tick (ops/tend.py); a failure is logged and the next minute comes."""
    while True:
        await asyncio.sleep(IDLE_EVERY)
        try:
            await tend.tend(engine, redis, cloudflare)
        except Exception:
            logging.getLogger("glyphh.tick").exception("tick failed")


def create_app(settings: Settings | None = None, http: httpx.AsyncClient | None = None) -> FastAPI:
    cfg: Settings = settings or get_settings()
    configure(cfg.log_level)
    if len(cfg.secret_key) < 32:
        raise RuntimeError("GLYPHH_SECRET_KEY must be set, 32 characters or more: it signs every sign-in step.")
    engine = make_engine(cfg.database_url)
    redis = make_redis(cfg.redis_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.http = http or httpx.AsyncClient(timeout=10)
        cloudflare = Cloudflare(app.state.http, cfg.cloudflare_api_token) if cfg.cloudflare_api_token else None
        idle = asyncio.create_task(tend_forever(engine, redis, cloudflare))
        flushing = asyncio.create_task(metrics.flush_forever(app.state.metrics, redis))
        yield
        await metrics.stop(flushing, app.state.metrics, redis)
        idle.cancel()
        with suppress(asyncio.CancelledError):
            await idle
        await app.state.http.aclose()
        await redis.aclose()
        await engine.dispose()

    app = FastAPI(
        title="Glyphh", version=cfg.version, lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.settings = cfg
    app.state.engine = engine
    app.state.redis = redis
    errors.install(app)
    gone.install(app)
    for module in ROUTERS:
        app.include_router(module.router)
    _wrap(app, cfg)
    return app


def _wrap(app: FastAPI, cfg: Settings) -> None:
    """The outer layers, innermost first: CORS for the platform's read of a consent, the request metrics, then the
    trace. Warnings and errors are kept for staff as ops events (obs/events.py)."""
    app.state.metrics = metrics.Recorder()  # every request's route, status and time (obs/metrics.py)
    events.install(cfg.redis_url)
    app.add_middleware(ConsentCorsMiddleware, platform_origin=cfg.platform_base)
    app.add_middleware(metrics.MetricsMiddleware, recorder=app.state.metrics)
    app.add_middleware(TraceMiddleware)
