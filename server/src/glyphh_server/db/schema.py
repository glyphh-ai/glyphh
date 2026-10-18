"""Create the schema and seed it: run before the server starts, safe to run every time. The schema is one file,
schema.sql, run as it is; the seeds follow, since they read the Stripe prices from the environment."""

import asyncio
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.config import Settings, get_settings
from glyphh_server.db.drift import refuse_drift
from glyphh_server.db.engine import make_engine
from glyphh_server.db.seed import seed_mods, seed_plans
from glyphh_server.db.seed_rates import seed_rates

SCHEMA: Path = Path(__file__).with_name("schema.sql")
_LOCK: int = 0x67_6C_79_70  # one schema run at a time across processes booting together


async def run_sql(conn: AsyncConnection, sql: str) -> None:
    """Run a script of many statements, as psql would: asyncpg's simple protocol, inside this transaction."""
    raw = await conn.get_raw_connection()
    await raw.driver_connection.execute(sql)  # type: ignore[union-attr]


async def apply_schema(engine: AsyncEngine, settings: Settings) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": _LOCK})
        await run_sql(conn, SCHEMA.read_text())
        await conn.run_sync(refuse_drift)
        await seed_mods(conn)
        await seed_plans(conn, settings)
        await seed_rates(conn)


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    try:
        await apply_schema(engine, settings)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
