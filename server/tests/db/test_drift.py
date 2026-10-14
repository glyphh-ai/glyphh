import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.drift import missing_columns, refuse_drift


class Rollback(Exception):
    pass


async def test_a_database_behind_the_code_is_found_and_refused(engine: AsyncEngine) -> None:
    with pytest.raises(Rollback):
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE users DROP COLUMN name"))
            assert await conn.run_sync(missing_columns) == {"users": ["name"]}
            with pytest.raises(RuntimeError, match="docker compose down -v"):
                await conn.run_sync(refuse_drift)
            raise Rollback


async def test_a_current_database_passes(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        assert await conn.run_sync(missing_columns) == {}
