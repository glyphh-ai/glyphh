"""The health operation: the one service function the SDK, the API and MCP all call."""

from typing import Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db.engine import database_reachable


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    database: bool


async def health(engine: AsyncEngine, version: str) -> Health:
    database: bool = await database_reachable(engine)
    return Health(status="ok" if database else "degraded", version=version, database=database)
