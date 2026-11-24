"""Redis, for what is counted or queued on its way to Postgres: the request metrics, the ops events, the tick's
heartbeat and Ada Cloud's reads. Nothing kept lives here; Postgres holds the record. In production Redis runs on the
server's own Fly machine, beside the server."""

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
