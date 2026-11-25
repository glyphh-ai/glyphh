"""The minute tick's heartbeat, for the staff view's alert that it has stopped (admin/alerts.py): the time each tick
began, on Redis."""

import time

from redis.asyncio import Redis

KEY: str = "ops:tick:last"


async def beat(redis: Redis, now: float | None = None) -> None:
    await redis.set(KEY, str(time.time() if now is None else now))


async def last(redis: Redis) -> float | None:
    """When the last tick began (epoch seconds); None when none has since Redis started."""
    found = await redis.get(KEY)
    return None if found is None else float(found)
