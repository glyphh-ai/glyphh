"""Migrations: a database made from schema.sql records every migration without running it; one with production's
baseline shape runs each once, in order; and the baseline with every migration run is exactly what schema.sql makes."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import schema
from glyphh_server.db.engine import make_engine
from glyphh_server.db.schema import apply_schema, migrations, run_sql
from tests.conftest import ADMIN_URL, DATABASE_URL, SETTINGS, _fresh_database

BASELINE: Path = Path(__file__).with_name("baseline.sql")
MIGRATE_DB: str = "glyphh_migrate_test"
SETTINGS_HERE = SETTINGS.model_copy(
    update={"database_url": make_url(DATABASE_URL).set(database=MIGRATE_DB).render_as_string(hide_password=False)}
)

# The shape of a database, as Postgres reports it: every column, constraint, index, policy and row-level security
# switch in the public schema. A column's position is left out: a migration adds a column at the end of its table.
SHAPE: dict[str, str] = {
    "columns": """
        SELECT table_name, column_name, data_type, udt_name, is_nullable, column_default,
               character_maximum_length, numeric_precision, numeric_scale
        FROM information_schema.columns WHERE table_schema = 'public'""",
    "constraints": """
        SELECT c.conrelid::regclass::text, c.conname, c.contype, pg_get_constraintdef(c.oid)
        FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace WHERE n.nspname = 'public'""",
    "indexes": "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'",
    "policies": """
        SELECT tablename, policyname, cmd, roles::text, qual, with_check
        FROM pg_policies WHERE schemaname = 'public'""",
    "security": """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public' AND c.relkind = 'r'""",
}


async def _shape(engine: AsyncEngine) -> dict[str, list[Any]]:
    async with engine.connect() as conn:
        return {k: sorted(tuple(r) for r in await conn.execute(text(q))) for k, q in SHAPE.items()}


async def _recorded(engine: AsyncEngine) -> list[tuple[int, str]]:
    async with engine.connect() as conn:
        rows = await conn.execute(text("SELECT version, name FROM schema_migrations ORDER BY version"))
        return [tuple(r) for r in rows]  # type: ignore[misc]


@pytest.fixture
async def own() -> AsyncIterator[AsyncEngine]:
    """A database of its own, empty."""
    await _fresh_database(make_url(ADMIN_URL).set(database=MIGRATE_DB).render_as_string(hide_password=False))
    eng = make_engine(SETTINGS_HERE.database_url)
    yield eng
    await eng.dispose()


@pytest.fixture
async def baseline(own: AsyncEngine) -> AsyncEngine:
    """That database with production's shape when it began keeping its data, and no record of migrations."""
    async with own.begin() as conn:
        await run_sql(conn, BASELINE.read_text())
    return own


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(schema, "MIGRATIONS", tmp_path)
    return tmp_path


async def test_the_baseline_and_every_migration_make_what_schema_sql_makes(
    engine: AsyncEngine, baseline: AsyncEngine
) -> None:
    await apply_schema(baseline, SETTINGS_HERE)
    assert await _shape(baseline) == await _shape(engine)
    every = [(0, "baseline")] + [(n, p.stem) for n, p in migrations(schema.MIGRATIONS)]
    assert await _recorded(baseline) == every == await _recorded(engine)


async def test_a_new_database_records_every_migration_without_running_it(own: AsyncEngine, folder: Path) -> None:
    (folder / "0001_never_run.sql").write_text("SELECT 1 / 0;")
    (folder / "0002_nor_this.sql").write_text("SELECT 1 / 0;")
    await apply_schema(own, SETTINGS_HERE)
    assert await _recorded(own) == [(0, "baseline"), (1, "0001_never_run"), (2, "0002_nor_this")]


async def test_a_kept_database_runs_each_migration_once_in_order(baseline: AsyncEngine, folder: Path) -> None:
    async with baseline.begin() as conn:
        await conn.execute(text("INSERT INTO mods (slug, name, description) VALUES ('kept', 'Kept', 'Kept data')"))
    (folder / "0001_mods_note.sql").write_text("ALTER TABLE mods ADD COLUMN note TEXT;")
    await apply_schema(baseline, SETTINGS_HERE)
    await apply_schema(baseline, SETTINGS_HERE)  # run again, the ALTER would fail
    (folder / "0002_mods_note_set.sql").write_text("UPDATE mods SET note = 'noted' WHERE slug = 'kept';")
    await apply_schema(baseline, SETTINGS_HERE)
    assert await _recorded(baseline) == [(0, "baseline"), (1, "0001_mods_note"), (2, "0002_mods_note_set")]
    async with baseline.connect() as conn:
        assert (await conn.execute(text("SELECT note FROM mods WHERE slug = 'kept'"))).scalar() == "noted"


def test_migrations_are_named_and_numbered_from_0001_without_a_gap(tmp_path: Path) -> None:
    assert migrations(tmp_path / "none") == []
    (tmp_path / "0001_first.sql").write_text("")
    (tmp_path / "notes.txt").write_text("")
    assert migrations(tmp_path) == [(1, tmp_path / "0001_first.sql")]
    (tmp_path / "0003_third.sql").write_text("")
    with pytest.raises(RuntimeError, match="no gap or repeat"):
        migrations(tmp_path)
    (tmp_path / "0002-Second.sql").write_text("")
    with pytest.raises(RuntimeError, match="named NNNN_name"):
        migrations(tmp_path)
