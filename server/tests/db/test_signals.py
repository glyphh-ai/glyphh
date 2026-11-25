"""The Redis client: a connection Redis dropped is found before it is written to, and a lost one is tried once more."""

from redis.exceptions import ConnectionError as RedisConnectionError

from glyphh_server.db.signals import HEALTH_CHECK_SECONDS, make_redis


async def test_a_lost_connection_is_checked_for_and_tried_once_more() -> None:
    client = make_redis("redis://localhost:1")
    try:
        kwargs = client.connection_pool.connection_kwargs
        assert kwargs["health_check_interval"] == HEALTH_CHECK_SECONDS
        assert RedisConnectionError in kwargs["retry_on_error"]
        assert kwargs["retry"].get_retries() == 1
    finally:
        await client.aclose()
