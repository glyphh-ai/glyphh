from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

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
    mcp,
    me,
    mods,
    oauth,
    oauth_meta,
    oauth_pages,
    org,
    plans,
    routine_triggers,
    runtime,
    workspaces,
)
from glyphh_server.api.trace import TraceMiddleware
from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.db.signals import make_redis
from glyphh_server.obs.logs import configure
from glyphh_server.ops import github_app, vault
from glyphh_server.ops.license import load_key
from glyphh_server.ops.link.hub import Hub

ROUTERS = (
    health,
    device,
    device_pages,
    me,
    license,
    workspaces,
    org,
    mods,
    plans,
    billing,
    runtime,
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
        yield
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
    app.add_middleware(TraceMiddleware)
    return app
