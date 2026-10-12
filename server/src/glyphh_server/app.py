from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.applications import Starlette

from glyphh_server.api import (
    errors,
    health,
    invite_answers,
    link,
    machines,
    me,
    org,
    session,
    sign_in_pages,
    sign_in_screens,
    thread_work,
    threads,
)
from glyphh_server.api.trace import TraceMiddleware
from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.link.hub import Hub
from glyphh_server.mcp.server import make_mcp, mcp_http_app
from glyphh_server.obs.logs import configure


def create_app(settings: Settings | None = None, http: httpx.AsyncClient | None = None) -> FastAPI:
    cfg: Settings = settings or get_settings()
    configure(cfg.log_level)
    if len(cfg.secret_key) < 32:
        raise RuntimeError("GLYPHH_SECRET_KEY must be set, 32 characters or more: it signs every sign-in link.")
    engine = make_engine(cfg.database_url)
    mcp = make_mcp(engine, cfg)
    mcp_app = mcp_http_app(mcp)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.http = http or httpx.AsyncClient(timeout=10)
        async with mcp.session_manager.run():
            yield
        await app.state.http.aclose()
        await engine.dispose()

    app = FastAPI(title="Glyphh", version=cfg.version, lifespan=lifespan)
    app.state.settings = cfg
    app.state.engine = engine
    app.state.hub = Hub()
    errors.install(app)
    app.include_router(health.router)
    app.include_router(me.router)
    app.include_router(org.router)
    app.include_router(sign_in_pages.router)
    app.include_router(sign_in_screens.router)
    app.include_router(invite_answers.router)
    app.include_router(session.router)
    app.include_router(machines.router)
    app.include_router(threads.router)
    app.include_router(thread_work.router)
    app.include_router(link.router)
    app.router.routes.extend(mcp_app.routes)
    _layers(app, mcp_app, cfg)
    return app


def _layers(app: FastAPI, mcp_app: Starlette, cfg: Settings) -> None:
    # The MCP app's own middleware (bearer authentication, then the token in context) comes with its routes;
    # add_middleware puts each one outermost, so they go in reverse; then the trace layer, then CORS outermost,
    # so even a refusal or a crash answer carries its CORS headers.
    for layer in reversed(mcp_app.user_middleware):
        app.add_middleware(layer.cls, *layer.args, **layer.kwargs)
    app.add_middleware(TraceMiddleware, platform=cfg.platform)
    # The platform calls the API from its own address; it sends tokens in a header, never cookies.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.platform_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["authorization", "content-type", "x-request-id"],
        expose_headers=["x-request-id"],
    )
