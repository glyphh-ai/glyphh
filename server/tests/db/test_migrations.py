"""The schema step on the two databases there are. A new one is made with only the kept tables. Production's, which
still has the retired products' tables (tests/db/production_2026_11_18.sql is its schema on the day they were
retired, never edited), boots as it is: nothing is dropped, nothing dropped is made again, and its kept tables are
already what schema.sql makes. And migrations, numbered on from the ones folded into schema.sql."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server import winddown
from glyphh_server.db import schema
from glyphh_server.db.engine import make_engine
from glyphh_server.db.schema import FOLDED, apply_schema, migrations, run_sql
from tests.conftest import ADMIN_URL, DATABASE_URL, SETTINGS, _fresh_database

PRODUCTION: Path = Path(__file__).with_name("production_2026_11_18.sql")
MIGRATE_DB: str = "glyphh_migrate_test"
SETTINGS_HERE = SETTINGS.model_copy(
    update={"database_url": make_url(DATABASE_URL).set(database=MIGRATE_DB).render_as_string(hide_password=False)}
)
TABLES: str = "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
# The shape of the kept tables, as Postgres reports it: every column, constraint, index, policy and row-level
# security switch.
SHAPE: dict[str, str] = {
    "columns": """
        SELECT table_name, column_name, data_type, udt_name, is_nullable, column_default, ordinal_position
        FROM information_schema.columns WHERE table_schema = 'public' AND table_name = ANY(:kept)""",
    "constraints": """
        SELECT c.conrelid::regclass::text, c.conname, c.contype, pg_get_constraintdef(c.oid)
        FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE n.nspname = 'public' AND c.conrelid::regclass::text = ANY(:kept)""",
    "indexes": """
        SELECT tablename, indexname, indexdef FROM pg_indexes
        WHERE schemaname = 'public' AND tablename = ANY(:kept)""",
    "policies": """
        SELECT tablename, policyname, cmd, roles::text, qual, with_check
        FROM pg_policies WHERE schemaname = 'public' AND tablename = ANY(:kept)""",
    "security": """
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname = ANY(:kept)""",
}
KEPT: dict[str, list[str]] = {"kept": [t for t in winddown.KEEP if t != "schema_migrations"]}


async def _shape(engine: AsyncEngine) -> dict[str, list[Any]]:
    async with engine.connect() as conn:
        return {k: sorted(tuple(r) for r in await conn.execute(text(q), KEPT)) for k, q in SHAPE.items()}


async def _tables(engine: AsyncEngine) -> set[str]:
    async with engine.connect() as conn:
        return set((await conn.execute(text(TABLES))).scalars())


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


async def as_production(engine: AsyncEngine) -> None:
    """Production's shape on the day the products were retired: every table, and its record of the 14 migrations."""
    async with engine.begin() as conn:
        await run_sql(conn, schema.LEDGER)
        await run_sql(conn, PRODUCTION.read_text())
        for version in range(FOLDED + 1):
            await conn.execute(
                text("INSERT INTO schema_migrations (version, name) VALUES (:v, :n)"),
                {"v": version, "n": f"m{version}"},
            )


@pytest.fixture
async def production(own: AsyncEngine) -> AsyncEngine:
    await as_production(own)
    return own


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A migrations folder for a test to put its own in."""
    monkeypatch.setattr(schema, "MIGRATIONS", tmp_path)
    return tmp_path


async def test_a_boot_on_an_empty_database_makes_only_the_kept_tables(own: AsyncEngine) -> None:
    await apply_schema(own, SETTINGS_HERE)
    assert await _tables(own) == set(winddown.KEEP)
    assert await _recorded(own) == [(0, "baseline")]


async def test_a_boot_on_production_keeps_every_old_table_and_makes_none_again(
    engine: AsyncEngine, production: AsyncEngine
) -> None:
    assert await _tables(production) == set(winddown.KEEP) | set(winddown.DROP)
    async with production.begin() as conn:
        await conn.execute(
            text("INSERT INTO mods (slug, name, description) VALUES ('ada', 'Ada', 'Kept until dropped')")
        )
    await apply_schema(production, SETTINGS_HERE)
    await apply_schema(production, SETTINGS_HERE)  # every start
    assert await _tables(production) == set(winddown.KEEP) | set(winddown.DROP)
    async with production.connect() as conn:
        assert (await conn.execute(text("SELECT count(*) FROM mods"))).scalar_one() == 1
    assert len(await _recorded(production)) == FOLDED + 1
    assert await _shape(production) == await _shape(engine)  # the kept tables are what a new database gets


async def test_a_dropped_table_is_not_made_again_at_the_next_boot(production: AsyncEngine) -> None:
    async with production.begin() as conn:
        for name in winddown.DROP:
            await conn.execute(text(f'DROP TABLE public."{name}"'))
    await apply_schema(production, SETTINGS_HERE)
    assert await _tables(production) == set(winddown.KEEP)


async def test_a_new_database_records_a_migration_without_running_it(own: AsyncEngine, folder: Path) -> None:
    (folder / "0015_never_run.sql").write_text("SELECT 1 / 0;")
    await apply_schema(own, SETTINGS_HERE)
    assert await _recorded(own) == [(0, "baseline"), (15, "0015_never_run")]


async def test_a_kept_database_runs_each_new_migration_once_in_order(production: AsyncEngine, folder: Path) -> None:
    (folder / "0015_plans_note.sql").write_text("ALTER TABLE plans ADD COLUMN note TEXT;")
    await apply_schema(production, SETTINGS_HERE)
    await apply_schema(production, SETTINGS_HERE)  # run again, the ALTER would fail
    (folder / "0016_plans_note_set.sql").write_text("UPDATE plans SET note = 'noted';")
    await apply_schema(production, SETTINGS_HERE)
    assert (await _recorded(production))[-2:] == [(15, "0015_plans_note"), (16, "0016_plans_note_set")]
    async with production.connect() as conn:
        assert set((await conn.execute(text("SELECT note FROM plans"))).scalars()) == {"noted"}


async def test_a_database_with_tables_and_no_record_runs_the_migrations_it_finds(
    own: AsyncEngine, folder: Path
) -> None:
    async with own.begin() as conn:
        await run_sql(conn, PRODUCTION.read_text())
    (folder / "0015_plans_note.sql").write_text("ALTER TABLE plans ADD COLUMN note TEXT;")
    await apply_schema(own, SETTINGS_HERE)
    assert await _recorded(own) == [(0, "baseline"), (15, "0015_plans_note")]


def test_there_is_no_migration_today_and_the_next_is_numbered_after_the_folded_ones(tmp_path: Path) -> None:
    assert migrations(schema.MIGRATIONS) == [] and FOLDED == 14
    (tmp_path / "0015_first.sql").write_text("")
    (tmp_path / "notes.txt").write_text("")
    assert migrations(tmp_path) == [(15, tmp_path / "0015_first.sql")]
    (tmp_path / "0017_third.sql").write_text("")
    with pytest.raises(RuntimeError, match=r"0015, 0016, \.\.\. with no gap"):
        migrations(tmp_path)
    (tmp_path / "0016-Second.sql").write_text("")
    with pytest.raises(RuntimeError, match="named NNNN_name"):
        migrations(tmp_path)
    (tmp_path / "0016-Second.sql").unlink()
    (tmp_path / "0017_third.sql").unlink()
    (tmp_path / "0001_old.sql").write_text("")
    with pytest.raises(RuntimeError, match="with no gap"):
        migrations(tmp_path)
