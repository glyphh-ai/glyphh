"""What the server can measure of itself, for staff: Ada's queues (each stream's length, what its group has taken and
not answered, what it has not taken yet) and its workers (a consumer of the group seen within ALIVE_MS is alive: an
idle worker asks again every two seconds, a busy one claims its message again every one or ten), the minute tick's
last beat, Postgres's size and connections (its own statistics) and Redis's memory."""

import time
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from redis.exceptions import ResponseError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_ada.protocol import GROUP, STREAMS
from glyphh_server.obs import tick

ALIVE_MS: int = 30_000
SIZES: str = """
    SELECT c.relname, pg_total_relation_size(c.oid) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY 2 DESC, 1 LIMIT 10"""
ADA_BYTES: str = """
    SELECT coalesce(sum(pg_total_relation_size(c.oid)), 0) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname ~ '^ada_[0-9a-f]{32}$' AND c.relkind = 'r'"""


class Queue(BaseModel):
    stream: str
    length: int
    pending: int = Field(description="Taken by a worker, not answered yet")
    lag: int = Field(description="Not taken by any worker yet")
    consumers: int
    alive: int = Field(description="Workers seen within the last 30 seconds")


class Table(BaseModel):
    name: str
    bytes: int


class Database(BaseModel):
    size_bytes: int
    ada_bytes: int = Field(description="Every org's Ada schema together")
    connections: dict[str, int] = Field(description="This database's connections by state")
    max_connections: int
    tables: list[Table]


class RedisMemory(BaseModel):
    used_bytes: int
    peak_bytes: int
    max_bytes: int = Field(description="0: no limit set")
    keys: int


class Tick(BaseModel):
    last_at: datetime | None
    age_seconds: float | None


async def queue(redis: Redis, name: str, stream: str) -> Queue:
    try:
        groups = [g for g in await redis.xinfo_groups(stream) if g["name"] == GROUP]
        consumers = await redis.xinfo_consumers(stream, GROUP) if groups else []
        length = await redis.xlen(stream)
    except ResponseError:  # no stream yet: no worker has started
        return Queue(stream=name, length=0, pending=0, lag=0, consumers=0, alive=0)
    group = groups[0] if groups else {}
    return Queue(
        stream=name,
        length=length,
        pending=int(group.get("pending") or 0),
        lag=int(group.get("lag") or 0),
        consumers=len(consumers),
        alive=sum(1 for c in consumers if int(c["idle"]) < ALIVE_MS),
    )


async def queues(redis: Redis) -> list[Queue]:
    """The two front doors (sync, jobs), always; and each kernel's own stream once one exists (`sync:3.13.0`)."""
    found = [await queue(redis, name, stream) for name, stream in STREAMS.items()]
    for name, stream in STREAMS.items():
        kernels = sorted([s async for s in redis.scan_iter(match=f"{stream}:*", _type="stream")])
        found += [await queue(redis, f"{name}{s.removeprefix(stream)}", s) for s in kernels]
    return found


async def database(conn: AsyncConnection) -> Database:
    one = lambda sql: conn.execute(text(sql))  # noqa: E731
    size = (await one("SELECT pg_database_size(current_database())")).scalar_one()
    states = await one(
        "SELECT coalesce(state, 'other'), count(*) FROM pg_stat_activity WHERE datname = current_database() GROUP BY 1"
    )
    return Database(
        size_bytes=size,
        ada_bytes=(await one(ADA_BYTES)).scalar_one(),
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
