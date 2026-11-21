"""Files in an org's schema from the API's side (files.py is the workers'): an import's upload streamed in, a chunk a
row, in one transaction that holds the import's job row, so a file is never half there and never written under an
import that has started; an export's archive streamed out, a chunk a transaction. The API writes nothing else of an
org's schema: it sets the org (glyphh.org_id) as a worker does, so the schema's row-level security holds."""

import uuid
from collections.abc import AsyncIterable, AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_ada import limits
from glyphh_ada.pg import schema_for
from glyphh_server.errors import Conflict, NotFound, TooLarge

_ORG = text("SELECT set_config('glyphh.org_id', :org, true)")


async def _enter(conn: AsyncConnection, org: str) -> str:
    await conn.execute(_ORG, {"org": org})
    return schema_for(org)


async def _pieces(stream: AsyncIterable[bytes]) -> AsyncIterator[bytes]:
    held = bytearray()
    async for piece in stream:
        held += piece
        while len(held) >= limits.CHUNK:
            yield bytes(held[: limits.CHUNK])
            del held[: limits.CHUNK]
    if held:
        yield bytes(held)


async def store(engine: AsyncEngine, org: str, job: str, stream: AsyncIterable[bytes], most: int) -> int:
    """An import's file, whole, while its job waits for it (409 E_CONFLICT once it has started). Returns its size."""
    fid, size = uuid.UUID(job), 0
    async with engine.begin() as conn:
        schema = await _enter(conn, org)
        state = await conn.execute(text(f'SELECT state FROM "{schema}".jobs WHERE id = :id FOR UPDATE'), {"id": fid})
        if state.scalar() != "awaiting":
            raise Conflict("This import has its file already, or has ended: start another.", reason="import_started")
        await conn.execute(text(f'DELETE FROM "{schema}".files WHERE id = :id'), {"id": fid})
        insert = text(f'INSERT INTO "{schema}".files (id, n, data) VALUES (:id, :n, :data)')
        n = 0
        async for piece in _pieces(stream):
            size += len(piece)
            if size > most:
                raise TooLarge(f"An import's file is at most {most} bytes.", max=most)
            await conn.execute(insert, {"id": fid, "n": n, "data": piece})
            n += 1
    return size


async def exists(engine: AsyncEngine, org: str, job: str) -> None:
    async with engine.begin() as conn:
        schema = await _enter(conn, org)
        found = await conn.execute(
            text(f'SELECT 1 FROM "{schema}".files WHERE id = :id AND n = 0'), {"id": uuid.UUID(job)}
        )
        if found.first() is None:
            raise NotFound("This file is gone: export again for a new link.")


async def pieces(engine: AsyncEngine, org: str, job: str) -> AsyncIterator[bytes]:
    """An export's archive, a chunk at a time, each read in a transaction of its own."""
    fid, n = uuid.UUID(job), 0
    while True:
        async with engine.begin() as conn:
            schema = await _enter(conn, org)
            got = await conn.execute(
                text(f'SELECT data FROM "{schema}".files WHERE id = :id AND n = :n'), {"id": fid, "n": n}
            )
            data = got.scalar()
        if data is None:
            return
        yield bytes(data)
        n += 1
