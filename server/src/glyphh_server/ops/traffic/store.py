"""What a traffic pull writes: a zone's row, its days' numbers and its days' tops. Cloudflare's daily totals replace
what was kept (it may correct them); the adaptive numbers, which a plan lets the pull see only a window of (a day cut
short at the plan's reach), keep the larger of what was kept and what came, so a day once seen whole stays whole."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.models import TrafficDay, TrafficTop, TrafficZone

Days = dict[tuple[str, date, str], int]  # (host, day, metric) -> n
Tops = dict[tuple[str, date, str, str], int]  # (host, day, kind, key) -> n
CHUNK: int = 1000  # rows a statement: Postgres takes at most 32,767 parameters


async def zone(conn: AsyncConnection, name: str, zone_id: str, plan: str | None, at: datetime, avail: Any) -> None:
    values = {"name": name, "zone_id": zone_id, "plan": plan, "pulled_at": at, "available": avail}
    stmt = insert(TrafficZone).values(**values)
    await conn.execute(stmt.on_conflict_do_update(index_elements=["name"], set_={**values}))


async def _upsert(conn: AsyncConnection, table: Any, keys: list[str], rows: list[dict[str, Any]], larger: bool) -> None:
    for at in range(0, len(rows), CHUNK):
        stmt = insert(table).values(rows[at : at + CHUNK])
        n = func.greatest(table.n, stmt.excluded.n) if larger else stmt.excluded.n
        await conn.execute(stmt.on_conflict_do_update(index_elements=keys, set_={"n": n}))


async def days(conn: AsyncConnection, zone_name: str, found: Days, keep_larger: bool) -> None:
    rows = [{"zone": zone_name, "host": h, "day": d, "metric": m, "n": n} for (h, d, m), n in found.items()]
    await _upsert(conn, TrafficDay, ["zone", "host", "day", "metric"], rows, keep_larger)


async def tops(conn: AsyncConnection, zone_name: str, found: Tops, keep_larger: bool) -> None:
    rows = [
        {"zone": zone_name, "host": h, "day": d, "kind": k, "key": key, "n": n} for (h, d, k, key), n in found.items()
    ]
    await _upsert(conn, TrafficTop, ["zone", "host", "day", "kind", "key"], rows, keep_larger)
