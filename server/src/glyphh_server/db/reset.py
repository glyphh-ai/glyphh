"""The database made clean, by hand only (development, emergencies; never on deploy, since production keeps its data):
every table the server's role owns dropped, then the schema step as at every start, so the schema is made again from
schema.sql and seeded. It does nothing unless GLYPHH_RESET_DATABASE is set for that run:
`GLYPHH_RESET_DATABASE=1 python -m glyphh_server.db.reset`."""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings, get_settings
from glyphh_server.db.engine import make_engine
from glyphh_server.db.schema import _LOCK, apply_schema, run_sql

log = logging.getLogger("glyphh.reset")

DROP_ALL: str = """
DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tableowner = current_user LOOP
    EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', t.tablename);
  END LOOP;
END $$;
"""


async def reset(engine: AsyncEngine, settings: Settings) -> None:
    """Drop the server's tables (and anything left from an older schema), then the schema step as at every start."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": _LOCK})
        await run_sql(conn, DROP_ALL)
    await apply_schema(engine, settings)


async def main(settings: Settings | None = None) -> bool:
    """Reset when GLYPHH_RESET_DATABASE is on; say so either way. True when it reset."""
    settings = settings or get_settings()
    if not settings.reset_database:
        log.warning("database kept: GLYPHH_RESET_DATABASE is not set")
        return False
    engine = make_engine(settings.database_url)
    try:
        await reset(engine, settings)
    finally:
        await engine.dispose()
    log.warning("database reset: every table dropped and made again from schema.sql")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
