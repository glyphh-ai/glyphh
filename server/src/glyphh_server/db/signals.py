"""Redis, for live signals only: pub/sub to whichever server process holds a person's connection. Nothing kept lives
here; Postgres holds the record. In production Redis runs on the server's own Fly machine, beside the server."""

import json
from typing import Any

from redis.asyncio import Redis

CONNECT_TIMEOUT: float = 2.0


def make_redis(url: str) -> Redis:
    """A client whose connections open on first use."""
    return Redis.from_url(url, decode_responses=True, socket_connect_timeout=CONNECT_TIMEOUT)


async def redis_reachable(redis: Redis) -> bool:
    try:
        await redis.ping()
    except Exception:  # noqa: BLE001  # any refusal means Redis is not reachable
        return False
    return True


async def publish(redis: Redis, channel: str, event: str, data: dict[str, Any]) -> int:
    """Send one event on a channel; the answer is how many connections heard it (0: nobody is listening)."""
    return int(await redis.publish(channel, json.dumps({"event": event, "data": data}, default=str)))
