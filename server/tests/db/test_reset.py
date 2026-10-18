"""The reset: on a database of its own, every table dropped and made again, seeded; nothing without the setting."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.engine import make_engine
from glyphh_server.db.reset import main
from glyphh_server.db.schema import apply_schema
from glyphh_server.models import Plan
from tests.conftest import ADMIN_URL, DATABASE_URL, SETTINGS, _fresh_database

RESET_DB: str = "glyphh_reset_test"
SETTINGS_HERE = SETTINGS.model_copy(
    update={"database_url": make_url(DATABASE_URL).set(database=RESET_DB).render_as_string(hide_password=False)}
)


@pytest.fixture
async def own() -> AsyncIterator[AsyncEngine]:
    await _fresh_database(make_url(ADMIN_URL).set(database=RESET_DB).render_as_string(hide_password=False))
    eng = make_engine(SETTINGS_HERE.database_url)
    await apply_schema(eng, SETTINGS_HERE)
    yield eng
    await eng.dispose()


async def _plans(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as conn:
        return list((await conn.execute(select(Plan.name).order_by(Plan.sort))).scalars())


async def test_a_reset_drops_every_table_and_makes_the_schema_again(own: AsyncEngine) -> None:
    async with own.begin() as conn:
        await conn.execute(insert(Plan).values(name="Trial", sort=9))
        await conn.execute(text("CREATE TABLE left_over (id int)"))
    assert await main(SETTINGS_HERE.model_copy(update={"reset_database": True})) is True
    assert await _plans(own) == ["Free", "Pro", "Team"]
    async with own.connect() as conn:
        assert (await conn.execute(text("SELECT to_regclass('public.left_over')"))).scalar() is None


async def test_without_the_setting_nothing_is_touched(own: AsyncEngine) -> None:
    async with own.begin() as conn:
        await conn.execute(insert(Plan).values(name="Trial", sort=9))
    assert await main(SETTINGS_HERE) is False
    assert "Trial" in await _plans(own)


async def test_the_reset_runs_as_a_module_and_keeps_the_data_unless_told(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio
    import runpy
    import warnings

    monkeypatch.delenv("GLYPHH_RESET_DATABASE", raising=False)

    def run() -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # the module is imported already; that's fine here
            runpy.run_module("glyphh_server.db.reset", run_name="__main__")

    await asyncio.to_thread(run)
