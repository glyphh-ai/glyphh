"""Create the schema and the Glyphh parent org: run before the server starts, safe to run every time."""

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import get_settings
from glyphh_server.db import make_engine
from glyphh_server.models import Base

_LOCK: int = 0x67_6C_79_70  # one schema run at a time across processes booting together
PARENT_ORG: str = "Glyphh"


async def apply_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": _LOCK})
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text("INSERT INTO orgs (name) VALUES (:name) ON CONFLICT ((true)) WHERE parent_id IS NULL DO NOTHING"),
            {"name": PARENT_ORG},
        )


async def main() -> None:
    engine: AsyncEngine = make_engine(get_settings().database_url)
    try:
        await apply_schema(engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
