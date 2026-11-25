"""Redis, for what is counted or queued on its way to Postgres: the request metrics, the ops events, the tick's
heartbeat and Ada Cloud's reads. Nothing kept lives here; Postgres holds the record. In production Redis runs on the
server's own Fly machine, beside the server."""

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import ConnectionError as RedisConnectionError

CONNECT_TIMEOUT: float = 2.0
# A connection idle this long is pinged before it is used, so one Redis dropped (it restarts with the machine) is
# found and reopened instead of written to.
HEALTH_CHECK_SECONDS: int = 15


def make_redis(url: str) -> Redis:
    """A client whose connections open on first use. A command that finds its connection lost is tried once more on
    a new one: the tick's hourly parts hold a connection idle for longer than Redis may live."""
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=CONNECT_TIMEOUT,
        health_check_interval=HEALTH_CHECK_SECONDS,
        retry=Retry(NoBackoff(), 1),
        retry_on_error=[RedisConnectionError],
    )


async def redis_reachable(redis: Redis) -> bool:
    try:
        await redis.ping()
    except Exception:  # noqa: BLE001  # any refusal means Redis is not reachable
        return False
    return True
