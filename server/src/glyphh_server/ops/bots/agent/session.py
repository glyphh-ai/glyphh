"""A live run's Agent SDK session, kept in Postgres (docs/specs/bot-agent-loop.md, 2.1): the SDK's SessionStore
(`append`, `load`), one line of the transcript a row, in the order written, so a run that waits on the person is
carried on from its own conversation after a deploy, a restart or on another machine. One store is one run's: the
SDK's project key (the run's folder) is not kept. A session goes when its run ends."""

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import BotSession


class Sessions:
    def __init__(self, engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID) -> None:
        self.engine, self.org_id, self.run_id = engine, org_id, run_id

    def _of(self, key: dict[str, Any]) -> tuple[Any, ...]:
        mine = (BotSession.run_id == self.run_id, BotSession.session_id == key["session_id"])
        return (*mine, BotSession.subpath == (key.get("subpath") or ""))

    async def append(self, key: dict[str, Any], entries: list[dict[str, Any]]) -> None:
        if not entries:
            return
        said = {"org_id": self.org_id, "run_id": self.run_id, "session_id": key["session_id"]}
        rows = [{**said, "subpath": key.get("subpath") or "", "entry": e} for e in entries]
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, self.org_id)
            await conn.execute(BotSession.__table__.insert(), rows)

    async def load(self, key: dict[str, Any]) -> list[dict[str, Any]] | None:
        async with self.engine.begin() as conn:
            await tenancy.enter(conn, self.org_id)
            found = await conn.execute(select(BotSession.entry).where(*self._of(key)).order_by(BotSession.id))
            entries = [dict(r.entry) for r in found]
        return entries or None


async def drop(engine: AsyncEngine, org_id: uuid.UUID, run_id: uuid.UUID) -> None:
    """The run's session, gone: its run ended."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        await conn.execute(delete(BotSession).where(BotSession.run_id == run_id))
