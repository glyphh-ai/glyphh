"""Whether the server, its database and its Redis answer."""

from typing import Literal

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.engine import database_reachable
from glyphh_server.db.signals import redis_reachable


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: bool
    redis: bool


async def health(engine: AsyncEngine, redis: Redis, version: str) -> Health:
    database: bool = await database_reachable(engine)
    live: bool = await redis_reachable(redis)
    status = "ok" if database and live else "degraded"
    return Health(status=status, version=version, database=database, redis=live)
