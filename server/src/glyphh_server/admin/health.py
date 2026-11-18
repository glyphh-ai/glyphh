"""The staff view's infrastructure page: the API's latency (the last 5 minutes, the last hour and hour by hour),
requests by route with their errors, Postgres, Redis, the tick, and the alerts they raise (admin/alerts.py).

The platform's page still shows the retired products' parts (Ada's queues, read latency and jobs): those keys are
answered empty until its screen drops them."""

from collections import Counter
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.admin import infra
from glyphh_server.admin.alerts import THRESHOLDS, Alert, alerts
from glyphh_server.obs import events_store, latency
from glyphh_server.obs.latency import Endpoint, Percentiles
from glyphh_server.obs.metrics import KIND

HOURS: int = 24
ROUTES: int = 30
NONE: Percentiles = latency.summary(Counter())


class Hour(BaseModel):
    hour: str
    latency: Percentiles


class Latency(BaseModel):
    last_5m: Percentiles = NONE
    last_hour: Percentiles = NONE
    hourly: list[Hour] = []


class HttpHour(BaseModel):
    hour: str
    total: int
    c5xx: int


class Http(BaseModel):
    total: int
    c5xx: int
    routes: list[Endpoint]
    hourly: list[HttpHour]


class Infra(BaseModel):
    alerts: list[Alert]
    thresholds: dict[str, float]
    tick: infra.Tick
    api: Latency
    http: Http
    database: infra.Database
    redis: infra.RedisMemory
    ada_cloud: bool = Field(False, description="Retired with the products: always false")
    queues: list[Any] = Field([], description="Retired with the products: always empty")
    read: Latency = Field(Latency(), description="Retired with the products: always empty")
    jobs: list[Any] = Field([], description="Retired with the products: always empty")


async def _latency(redis: Redis) -> Latency:
    hourly = [Hour(hour=h, latency=p) for h, p in await latency.hourly(redis, KIND, HOURS)]
    return Latency(
        last_5m=await latency.window(redis, KIND, 5), last_hour=await latency.window(redis, KIND, 60), hourly=hourly
    )


async def _http(redis: Redis) -> Http:
    routes = await latency.http_window(redis, 60)
    names = latency.hours(HOURS)
    found = await latency.hashes(redis, (f"ops:http:h:{h}" for h in names))
    hourly = [
        HttpHour(hour=h, total=c.total(), c5xx=sum(n for k, n in c.items() if k.endswith("|5xx")))
        for h, c in zip(names, found, strict=True)
    ]
    return Http(
        total=sum(r.total for r in routes), c5xx=sum(r.c5xx for r in routes), routes=routes[:ROUTES], hourly=hourly
    )


async def current_alerts(conn: AsyncConnection, redis: Redis) -> list[Alert]:
    """The alerts alone, for the dashboard's top."""
    return alerts(
        await latency.http_window(redis, 5),
        await infra.last_tick(redis),
        await events_store.open_counts(conn, timedelta(hours=1)),
    )


async def health(conn: AsyncConnection, redis: Redis) -> Infra:
    return Infra(
        alerts=await current_alerts(conn, redis),
        thresholds=THRESHOLDS,
        tick=await infra.last_tick(redis),
        api=await _latency(redis),
        http=await _http(redis),
        database=await infra.database(conn),
        redis=await infra.memory(redis),
    )
