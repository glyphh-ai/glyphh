"""The person's approvals as server-sent events, for the glyphh mod while Claude is open.

The stream listens on the person's channel first, then replays the approvals already waiting, so nothing asked in
between is missed (it may come twice; the id tells). A comment line every 20 seconds keeps idle proxies from closing
it. When the person goes, the stream stops listening and gives its Redis connection back."""

import json
from collections.abc import AsyncIterator

import anyio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.ops.approvals import channel, waiting
from glyphh_server.ops.auth.principal import Principal

HEARTBEAT: float = 20.0


def event(name: str, data: str) -> str:
    """One server-sent event; data is already JSON, one line."""
    return f"event: {name}\ndata: {data}\n\n"


async def _replay(engine: AsyncEngine, who: Principal) -> list[str]:
    """The approvals waiting now, read as the caller's org in a transaction of its own, not held by the stream."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        views = await waiting(conn, who.user_id)
    return [event("approval", v.model_dump_json()) for v in views]


async def stream(engine: AsyncEngine, redis: Redis, who: Principal, heartbeat: float = HEARTBEAT) -> AsyncIterator[str]:
    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(channel(who.user_id))
        for line in await _replay(engine, who):
            yield line
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=heartbeat)
            if message is None:
                yield ": heartbeat\n\n"
                continue
            signal = json.loads(message["data"])
            yield event(signal["event"], json.dumps(signal["data"], separators=(",", ":")))
    finally:
        # The hang-up cancels the stream; shielded, the connection still goes back to the pool.
        with anyio.CancelScope(shield=True):
            await pubsub.aclose()
