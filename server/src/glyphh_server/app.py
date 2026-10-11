from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from glyphh_server.api import errors, health, me
from glyphh_server.api.trace import TraceMiddleware
from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.mcp.server import make_mcp, mcp_http_app
from glyphh_server.obs.logs import configure


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg: Settings = settings or get_settings()
    configure(cfg.log_level)
    if len(cfg.secret_key) < 32:
        raise RuntimeError("GLYPHH_SECRET_KEY must be set, 32 characters or more: it signs every sign-in link.")
    engine = make_engine(cfg.database_url)
    mcp = make_mcp(engine, cfg)
    mcp_app = mcp_http_app(mcp)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with mcp.session_manager.run():
            yield
        await engine.dispose()

    app = FastAPI(title="Glyphh", version=cfg.version, lifespan=lifespan)
    app.state.settings = cfg
    app.state.engine = engine
    errors.install(app)
    app.include_router(health.router)
    app.include_router(me.router)
    app.router.routes.extend(mcp_app.routes)
    # The MCP app's own middleware (bearer authentication, then the token in context) comes with its routes;
    # add_middleware puts each one outermost, so they go in reverse, and the trace layer goes last: outermost.
    for layer in reversed(mcp_app.user_middleware):
        app.add_middleware(layer.cls, *layer.args, **layer.kwargs)
    app.add_middleware(TraceMiddleware)
    return app
