"""A model day by day, for the platform's dashboard (GET /v1/models/{name}/stats): its reads by kind, and what its
decides answered, each output apart: how many, how many asked a person, and how sure they were (the decided outcome's
probability, in tenths). Days are UTC. A named output's metrics end `|<output>` (`decided|team`); the default
output's have none.

Counted in Redis as they happen, in one hash per org of what the database has not been told yet (`ada:days:<org>`,
fields `<YYYY-MM-DD>|<model>|<metric>`, with the org in `ada:days:orgs`): a read where it is counted (api/meter.py,
in the round trip that counts it against the month), a decide's answer by its worker once it has replied
(loop.py), so neither read waits on it. The server's minute tick takes each org's hash whole and adds it to
ada_model_days; losing Redis loses at most a minute of them. The dashboard adds what Redis holds that the tick has
not taken yet (daily), so a read shows the moment it is counted."""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import AdaModelDay, Org

ORGS: str = "ada:days:orgs"
DECIDED, ASKED, SURE = "decided", "asked", "sure:"
# The org's hash and its place in the set, taken at once: a count made after it starts a new hash and set entry.
TAKE: str = """
local held = redis.call('HGETALL', KEYS[1])
redis.call('DEL', KEYS[1])
redis.call('SREM', KEYS[2], ARGV[1])
return held
"""


def key(org: object) -> str:
    return f"ada:days:{org}"


def today(now: datetime | None = None) -> str:
    return (now or datetime.now(UTC)).strftime("%Y-%m-%d")


def field(model: str, metric: str, day: str | None = None) -> str:
    return f"{day or today()}|{model}|{metric}"


def count(pipe: Any, org: object, model: str, op: str, n: int) -> Any:
    """A model's reads of a kind added to the pipeline that counts them against the month (n < 0 takes them back)."""
    return pipe.hincrby(key(org), field(model, f"read:{op}"), n).sadd(ORGS, str(org))


def of(metric: str, output: str | None) -> str:
    """A metric of one output: the default's as it is, a named one's with `|<output>`."""
    return metric if output is None else f"{metric}|{output}"


def split(metric: str) -> tuple[str, str | None]:
    """A metric and the output it is of (None: the default)."""
    name, _, output = metric.partition("|")
    return name, output or None


def decided(redis: Any, org: str, model: str, answer: dict[str, Any], output: str | None = None) -> None:
    """A decide's answer, each output's apart (`output`: the one it was asked for, when it decided one): decided,
    whether it asked, how sure, in tenths."""
    pipe, h = redis.pipeline(transaction=False), key(org)
    answers = answer["outputs"].items() if "outputs" in answer else [(output, answer)]
    for name, out in answers:
        pipe.hincrby(h, field(model, of(DECIDED, name)), 1)
        if out.get("ask"):
            pipe.hincrby(h, field(model, of(ASKED, name)), 1)
        sure = (out.get("probabilities") or {}).get(out.get("outcome"))
        if sure is not None:
            pipe.hincrby(h, field(model, of(f"{SURE}{min(9, int(float(sure) * 10))}", name)), 1)
    pipe.sadd(ORGS, org).execute()


async def _add(engine: AsyncEngine, org: uuid.UUID, rows: list[dict[str, Any]]) -> bool:
    """The counts added to the org's days; False when the org is gone (its counts go with it)."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, org)
        if (await conn.execute(select(Org.id).where(Org.id == org))).first() is None:
            return False
        made = upsert(AdaModelDay).values(rows)
        more = {"n": AdaModelDay.n + made.excluded.n}
        keys = [AdaModelDay.org_id, AdaModelDay.model, AdaModelDay.day, AdaModelDay.metric]
        await conn.execute(made.on_conflict_do_update(index_elements=keys, set_=more))
    return True


def _rows(org: uuid.UUID, flat: list[str]) -> list[dict[str, Any]]:
    rows = []
    for name, n in zip(flat[::2], flat[1::2], strict=True):
        day, model, metric = name.split("|", 2)
        if int(n):
            rows.append({"org_id": org, "model": model, "day": date.fromisoformat(day), "metric": metric, "n": int(n)})
    return rows


async def flush(engine: AsyncEngine, redis: Redis) -> int:
    """Every org's counts the database has not been told of, added to ada_model_days; answers how many rows. An org's
    counts the database could not take go back to Redis for the next tick."""
    added = 0
    for org in await redis.smembers(ORGS):  # type: ignore[misc]
        flat = await redis.eval(TAKE, 2, key(org), ORGS, org)  # type: ignore[misc]
        rows = _rows(uuid.UUID(org), flat)
        try:
            if rows and await _add(engine, uuid.UUID(org), rows):
                added += len(rows)
        except Exception:
            async with redis.pipeline(transaction=True) as pipe:
                for row in rows:
                    pipe.hincrby(key(org), field(row["model"], row["metric"], row["day"].isoformat()), row["n"])
                await pipe.sadd(ORGS, org).execute()
            raise
    return added


async def pending(redis: Redis, org: uuid.UUID, model: str) -> list[tuple[date, str, int]]:
    """The model's counts in Redis that the tick has not taken into the database yet."""
    held = await redis.hgetall(key(org))  # type: ignore[misc]
    rows = _rows(org, [x for pair in held.items() for x in pair])
    return [(r["day"], r["metric"], r["n"]) for r in rows if r["model"] == model]


async def daily(
    conn: AsyncConnection, redis: Redis, org: uuid.UUID, model: str, since: date
) -> dict[date, dict[str, int]]:
    """The model's counts by day from `since`: the database's, on a connection that has entered its org, and Redis's
    that the tick has not taken yet (a minute's, or more while the tick cannot reach the database)."""
    found = select(AdaModelDay.day, AdaModelDay.metric, AdaModelDay.n).where(
        AdaModelDay.org_id == org, AdaModelDay.model == model, AdaModelDay.day >= since
    )
    out: dict[date, dict[str, int]] = {}
    for day, metric, n in [*(await conn.execute(found)).all(), *await pending(redis, org, model)]:
        if day >= since:
            held = out.setdefault(day, {})
            held[metric] = held.get(metric, 0) + int(n)
    return out
