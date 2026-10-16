import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import timedelta

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.api import (
    addons,
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
    unlock,
)
from glyphh_server.api.consent_cors import ConsentCorsMiddleware
from glyphh_server.api.trace import TraceMiddleware
from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.db.signals import make_redis
from glyphh_server.obs.logs import configure
from glyphh_server.ops import github_app, hosted, hours, vault
from glyphh_server.ops.fly import Fly
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
    addons,
    billing,
    runtime,
    models,
    unlock,
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


async def tend_forever(engine: AsyncEngine, fly: Fly, hub: Hub, idle: timedelta) -> None:
    """Every minute, tally the hosted runtimes' hours (pausing those past their plan's) and stop the idle ones; a
    failure is logged and the next minute comes."""
    while True:
        await asyncio.sleep(IDLE_EVERY)
        try:
            await hours.tend(engine, fly, hub, idle, int(IDLE_EVERY))
        except Exception:
            logging.getLogger("glyphh.runtime").exception("tending hosted runtimes failed")


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
        idle: asyncio.Task[None] | None = None
        if cfg.fly_configured:
            fly = Fly(app.state.http, cfg)
            app.state.hub.waker = hosted.waker(engine, fly)
            minutes = timedelta(minutes=cfg.runtime_idle_minutes)
            idle = asyncio.create_task(tend_forever(engine, fly, app.state.hub, minutes))
        yield
        if idle is not None:
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
    app.state.license_key = load_key(cfg)
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
