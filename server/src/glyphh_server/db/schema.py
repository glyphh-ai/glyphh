"""Create the schema, migrate it and seed it: run before the server starts, safe to run every time. schema.sql is the
schema's latest shape, run as it is; db/migrations/NNNN_name.sql bring a database that has data forward to it, each
once, in order, recorded in schema_migrations. A database with no tables yet is made from schema.sql, every migration
recorded without running; one with tables but no record has production's shape when it began keeping its data
(tests/db/baseline.sql), so every migration runs on it. The seeds follow, since they read the Stripe prices from the
environment."""

import asyncio
import logging
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.config import Settings, get_settings
from glyphh_server.db.drift import refuse_drift
from glyphh_server.db.engine import make_engine
from glyphh_server.db.seed import seed_mods, seed_plans
from glyphh_server.db.seed_clients import seed_platform_client
from glyphh_server.ops.templates.library import seed_templates

log = logging.getLogger("glyphh.schema")

SCHEMA: Path = Path(__file__).with_name("schema.sql")
MIGRATIONS: Path = Path(__file__).with_name("migrations")
_LOCK: int = 0x67_6C_79_70  # one schema run at a time across processes booting together
_NAME = re.compile(r"(\d{4})_[a-z0-9_]+\.sql")

LEDGER: str = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER NOT NULL,
    name TEXT NOT NULL,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (version)
);
"""
_HAS_TABLES: str = (
    "SELECT EXISTS (SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'schema_migrations')"
)


async def run_sql(conn: AsyncConnection, sql: str) -> None:
    """Run a script of many statements, as psql would: asyncpg's simple protocol, inside this transaction."""
    raw = await conn.get_raw_connection()
    await raw.driver_connection.execute(sql)  # type: ignore[union-attr]


def migrations(folder: Path) -> list[tuple[int, Path]]:
    """The migrations in order, numbered from 0001 with no gap or repeat; anything else stops the start."""
    found = []
    for path in sorted(folder.glob("*.sql")):
        match = _NAME.fullmatch(path.name)
        if not match:
            raise RuntimeError(f"A migration is named NNNN_name.sql, in lower case: {path.name}")
        found.append((int(match[1]), path))
    if [n for n, _ in found] != list(range(1, len(found) + 1)):
        names = [p.name for _, p in found]
        raise RuntimeError(f"Migrations are numbered 0001, 0002, ... with no gap or repeat: {names}")
    return found


async def _record(conn: AsyncConnection, version: int, name: str) -> None:
    await conn.execute(text("INSERT INTO schema_migrations (version, name) VALUES (:v, :n)"), {"v": version, "n": name})


async def migrate(conn: AsyncConnection) -> None:
    """Bring this database to schema.sql's shape: the migrations it has not had, in order, then schema.sql itself."""
    await run_sql(conn, LEDGER)
    pending = migrations(MIGRATIONS)
    done = set((await conn.execute(text("SELECT version FROM schema_migrations"))).scalars())
    if not done:
        fresh = not (await conn.execute(text(_HAS_TABLES))).scalar()
        await _record(conn, 0, "baseline")
        done = {0}
        if fresh:  # schema.sql, below, makes the latest shape: every migration is in it already
            for version, path in pending:
                await _record(conn, version, path.stem)
                done.add(version)
    for version, path in pending:
        if version not in done:
            await run_sql(conn, path.read_text())
            await _record(conn, version, path.stem)
            log.warning("migrated: %s", path.name)
    await run_sql(conn, SCHEMA.read_text())


async def apply_schema(engine: AsyncEngine, settings: Settings) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": _LOCK})
        await migrate(conn)
        await conn.run_sync(refuse_drift)
        await seed_mods(conn)
        await seed_plans(conn, settings)
        await seed_platform_client(conn, settings)
        await seed_templates(conn)


async def main() -> None:
    settings = get_settings()
    engine = make_engine(settings.database_url)
    try:
        await apply_schema(engine, settings)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
