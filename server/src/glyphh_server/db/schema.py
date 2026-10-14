"""Create the schema and seed it: run before the server starts, safe to run every time."""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings, get_settings
from glyphh_server.db.drift import refuse_drift
from glyphh_server.db.engine import make_engine
from glyphh_server.db.seed import seed_mods, seed_plans
from glyphh_server.db.tenancy import apply_tenancy
from glyphh_server.models import Base

_LOCK: int = 0x67_6C_79_70  # one schema run at a time across processes booting together


async def apply_schema(engine: AsyncEngine, settings: Settings) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": _LOCK})
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(refuse_drift)
        await apply_tenancy(conn)
        await seed_mods(conn)
        await seed_plans(conn, settings)


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    try:
        await apply_schema(engine, settings)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
