"""What the server can measure of itself, for staff: the minute tick's last beat, Postgres's size and connections
(its own statistics) and Redis's memory."""

import time
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.obs import tick

SIZES: str = """
    SELECT c.relname, pg_total_relation_size(c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY 2 DESC, 1 LIMIT 10"""


class Table(BaseModel):
    name: str
    bytes: int


class Database(BaseModel):
    size_bytes: int
    connections: dict[str, int] = Field(description="This database's connections by state")
    max_connections: int
    tables: list[Table]
    ada_bytes: int = Field(0, description="Retired with the products: always 0")


class RedisMemory(BaseModel):
    used_bytes: int
    peak_bytes: int
    max_bytes: int = Field(description="0: no limit set")
    keys: int


class Tick(BaseModel):
    last_at: datetime | None
    age_seconds: float | None


async def database(conn: AsyncConnection) -> Database:
    one = lambda sql: conn.execute(text(sql))  # noqa: E731
    size = (await one("SELECT pg_database_size(current_database())")).scalar_one()
    states = await one(
        "SELECT coalesce(state, 'other'), count(*) FROM pg_stat_activity WHERE datname = current_database() GROUP BY 1"
    )
    return Database(
        size_bytes=size,
        connections={s: int(n) for s, n in states},
        max_connections=int((await one("SELECT current_setting('max_connections')")).scalar_one()),
        tables=[Table(name=n, bytes=b) for n, b in await one(SIZES)],
    )


async def memory(redis: Redis) -> RedisMemory:
    info = await redis.info("memory")
    return RedisMemory(
        used_bytes=int(info.get("used_memory", 0)),
        peak_bytes=int(info.get("used_memory_peak", 0)),
        max_bytes=int(info.get("maxmemory", 0)),
        keys=int(await redis.dbsize()),
    )


async def last_tick(redis: Redis, now: float | None = None) -> Tick:
    at = await tick.last(redis)
    if at is None:
        return Tick(last_at=None, age_seconds=None)
    age = (time.time() if now is None else now) - at
    return Tick(last_at=datetime.fromtimestamp(at, UTC), age_seconds=round(age, 1))
