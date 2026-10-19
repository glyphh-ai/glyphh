import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.api import (
    approvals,
    billing,
    connector,
    device,
    device_pages,
    errors,
    github,
    github_pages,
    health,
    license,
    machines,
    mcp,
    me,
    models,
    mods,
    oauth,
    oauth_meta,
    oauth_pages,
    org,
    plans,
    routine_triggers,
    runtime,
    self_hosted,
)
from glyphh_server.api.consent_cors import ConsentCorsMiddleware
from glyphh_server.api.trace import TraceMiddleware
from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.db.signals import make_redis
from glyphh_server.obs.logs import configure
from glyphh_server.ops import github_app, tend, vault
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.fly import Fly
from glyphh_server.ops.idle import waker
from glyphh_server.ops.license import load_key
from glyphh_server.ops.link.hub import Hub

ROUTERS = (
    health,
    device,
    device_pages,
    me,
    license,
    org,
    mods,
    plans,
    billing,
    runtime,
    self_hosted,
    machines,  # after self_hosted: /v1/runtimes/self is not a machine's id
    models,
    routine_triggers,
    approvals,
    github,
    github_pages,
    oauth_meta,
    oauth,
    oauth_pages,
    connector,
    mcp,
)


IDLE_EVERY: float = 60.0


async def tend_forever(
    engine: AsyncEngine, hub: Hub, cfg: Settings, fly: Fly | None, stripe: StripeClient | None
) -> None:
    """Every minute, the server's tick (ops/tend.py); a failure is logged and the next minute comes."""
    while True:
        await asyncio.sleep(IDLE_EVERY)
        try:
            await tend.tend(engine, hub, cfg, int(IDLE_EVERY), fly, stripe)
        except Exception:
            logging.getLogger("glyphh.runtime").exception("tending hosted runtimes failed")


def _tending(app: FastAPI, cfg: Settings, engine: AsyncEngine) -> asyncio.Task[None]:
    """The minute tick, always; with hosting on, Fly and the hub's waker; with billing set up, Stripe's meter."""
    fly = Fly(app.state.http, cfg) if cfg.hosting_on else None
    if fly is not None:
        app.state.hub.waker = waker(engine, fly)
    meter = cfg.stripe_secret_key and StripeClient(app.state.http, cfg.stripe_secret_key, cfg.stripe_meter_hosting)
    return asyncio.create_task(tend_forever(engine, app.state.hub, cfg, fly, meter or None))


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
        idle = _tending(app, cfg, engine)
        yield
        idle.cancel()
        with suppress(asyncio.CancelledError):
            await idle
        await app.state.hub.close_all()
        await app.state.http.aclose()
        await redis.aclose()
        await engine.dispose()

    app = FastAPI(title="Glyphh", version=cfg.version, lifespan=lifespan)
    app.state.settings = cfg
    app.state.engine = engine
    app.state.redis = redis
    app.state.hub = Hub(redis)
    app.state.signing_key = load_key(cfg)
    app.state.secrets_key = vault.load_key(cfg)
    app.state.github_key = github_app.load_key(cfg)
    errors.install(app)
    for module in ROUTERS:
        app.include_router(module.router)
    _wrap(app, cfg)
    return app


def _wrap(app: FastAPI, cfg: Settings) -> None:
    """The outer layers, innermost first: CORS for the platform's read of a consent, then the trace."""
    app.add_middleware(ConsentCorsMiddleware, platform_origin=cfg.platform_base)
    app.add_middleware(TraceMiddleware)
