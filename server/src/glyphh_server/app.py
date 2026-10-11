from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from glyphh_server.api import errors, health
from glyphh_server.api.trace import TraceMiddleware
from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.mcp.server import make_mcp, mcp_http_app
from glyphh_server.obs.logs import configure


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg: Settings = settings or get_settings()
    configure(cfg.log_level)
    engine = make_engine(cfg.database_url)
    mcp = make_mcp(engine, cfg.version)
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
    app.add_middleware(TraceMiddleware)
    app.include_router(health.router)
    app.router.routes.extend(mcp_app.routes)
    return app
