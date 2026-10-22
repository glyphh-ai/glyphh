"""The Ada API: its own FastAPI app, reached only at the Ada hosts (GLYPHH_ADA_HOSTS, `ada.glyphh.ai`) and only with
GLYPHH_ADA_CLOUD on. It is a second host of glyphh-ai-server, not a second service: the same process, the same
database and Redis, its own clean paths (`/v1/models`, `/v1/decide`, `/v1/runs`) beside the account API's."""

from typing import Any

from fastapi import FastAPI
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.types import ASGIApp, Receive, Scope, Send

from glyphh_ada.api import cases, jobs, keys, models, reads, runs
from glyphh_server.api import errors, health
from glyphh_server.config import Settings

ROUTERS = (health, keys, models, cases, reads, jobs, runs)


def make_app(cfg: Settings, engine: AsyncEngine) -> FastAPI:
    """The Ada app, with a Redis client of its own: a call waits on its reply (BLPOP) longer than the server's
    client allows a read (redis-py's default socket timeout, 5 s), so this one sets none. The server closes it."""
    ada = FastAPI(title="Glyphh Ada", version=cfg.version)
    ada.state.settings, ada.state.engine = cfg, engine
    ada.state.redis = Redis.from_url(
        cfg.redis_url, decode_responses=True, socket_connect_timeout=2.0, socket_timeout=None
    )
    ada.state.ada_callers = {}  # api/auth.py's few seconds of resolved keys
    errors.install(ada)
    for module in ROUTERS:
        ada.include_router(module.router)
    return ada


def _host(scope: Scope) -> str:
    for name, value in scope.get("headers", []):
        if name == b"host":
            return value.decode("latin-1").rsplit(":", 1)[0].lower()
    return ""


class HostRouter:
    """A request whose Host is an Ada host goes to the Ada app; every other, and the lifespan, to the server's."""

    def __init__(self, app: ASGIApp, ada: ASGIApp, hosts: set[str]) -> None:
        self.app, self.ada, self.hosts = app, ada, hosts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> Any:
        if scope["type"] in ("http", "websocket") and _host(scope) in self.hosts:
            return await self.ada(scope, receive, send)
        return await self.app(scope, receive, send)
