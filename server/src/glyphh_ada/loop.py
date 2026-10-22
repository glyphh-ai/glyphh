"""One worker process's loop over its stream (protocol.STREAMS[queue]), as one consumer of the group `ada`: first a
message another worker took and stopped heartbeating (XAUTOCLAIM), else a new one (XREADGROUP). While it works, a
heartbeat thread claims its message again every second (sync) or ten (jobs), so only a dead worker's message is ever
taken over. A sync message past its deadline is dropped (the API has answered 504 already); one that has killed
MAX_DELIVERIES workers is answered E_INTERNAL. The message is acknowledged once it is answered."""

import logging
import threading
from collections.abc import Callable
from typing import Any

from redis import Redis
from redis.exceptions import ResponseError

from glyphh_ada import protocol
from glyphh_ada.errors import Refusal
from glyphh_ada.protocol import GROUP, SYNC, Message
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.ada")

BLOCK_MS: int = 2000
STALE_CONSUMER_MS: int = 86_400_000  # a consumer gone a day with nothing pending leaves the group


class Heartbeat:
    """Claims the message in hand again and again, keeping its idle time near zero while this worker lives."""

    def __init__(self, redis: Redis, stream: str, consumer: str, message_id: str, every: float) -> None:
        self.args, self.every, self.stop = (stream, GROUP, consumer, 0, [message_id]), every, threading.Event()
        self.redis, self.thread = redis, threading.Thread(target=self._beat, daemon=True)

    def _beat(self) -> None:
        while not self.stop.wait(self.every):
            self.redis.xclaim(*self.args, justid=True)

    def __enter__(self) -> "Heartbeat":
        self.thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop.set()
        self.thread.join()


class Loop:
    def __init__(
        self, queue: str, redis: Redis, consumer: str, dispatch: Callable[[Message], tuple[Any, int | None]]
    ) -> None:
        self.queue, self.redis, self.consumer, self.dispatch = queue, redis, consumer, dispatch
        self.stream = protocol.STREAMS[queue]

    def ensure_group(self) -> None:
        """The stream and its group, made once; consumers long gone with nothing pending removed."""
        try:
            self.redis.xgroup_create(self.stream, GROUP, id="0", mkstream=True)
        except ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise
        for c in self.redis.xinfo_consumers(self.stream, GROUP):
            if c["pending"] == 0 and c["idle"] > STALE_CONSUMER_MS:
                self.redis.xgroup_delconsumer(self.stream, GROUP, c["name"])

    def _next(self) -> tuple[str, dict[str, str] | None, bool] | None:
        idle = protocol.CLAIM_IDLE[self.queue]
        claimed = self.redis.xautoclaim(self.stream, GROUP, self.consumer, idle, start_id="0-0", count=1)
        if claimed[1]:
            return claimed[1][0][0], claimed[1][0][1], True
        got = self.redis.xreadgroup(GROUP, self.consumer, {self.stream: ">"}, count=1, block=BLOCK_MS)
        return (got[0][1][0][0], got[0][1][0][1], False) if got else None

    def one(self) -> bool:
        """Take and answer one message; False when none came."""
        found = self._next()
        if found is None:
            return False
        message_id, raw, claimed = found
        if raw:
            with Heartbeat(self.redis, self.stream, self.consumer, message_id, protocol.HEARTBEAT[self.queue]):
                self._answer(Message.of(raw), self._deliveries(message_id) if claimed else 1)
        self.redis.xack(self.stream, GROUP, message_id)
        return True

    def _deliveries(self, message_id: str) -> int:
        pending = self.redis.xpending_range(self.stream, GROUP, min=message_id, max=message_id, count=1)
        return int(pending[0]["times_delivered"]) if pending else 1

    def _answer(self, msg: Message, deliveries: int) -> None:
        about = fields(op=msg.op, org=msg.org, request=msg.id, deliveries=deliveries)
        if self.queue == SYNC and msg.expired:
            log.warning("dropped past its deadline", extra=about)
            return
        if deliveries > protocol.MAX_DELIVERIES:
            log.error("dropped: it stopped too many workers", extra=about)
            return self._reply(msg, protocol.refused("E_INTERNAL", "This request could not be answered.", 500))
        try:
            answer = protocol.ok(*self.dispatch(msg))
        except Refusal as r:
            answer = protocol.refused(r.code, r.message, r.status, **r.detail)
        except Exception:  # a crash is the caller's E_INTERNAL; the worker goes on
            log.exception("failed", extra=about)
            answer = protocol.refused("E_INTERNAL", "Something went wrong on our side.", 500, request=msg.id)
        self._reply(msg, answer)

    def _reply(self, msg: Message, answer: str) -> None:
        if self.queue == SYNC:
            key = protocol.reply_key(msg.id)
            self.redis.pipeline().lpush(key, answer).expire(key, protocol.REPLY_TTL).execute()
