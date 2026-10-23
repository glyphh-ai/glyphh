"""One worker process's loop over its streams, as one consumer of the group `ada`: its kernel's own stream
(`ada:sync:<kernel>`, routing.py) and, for the latest stable's workers, the front door (protocol.STREAMS[queue]).
First a message another worker took and stopped heartbeating (XAUTOCLAIM), else a new one (XREADGROUP). While it
works, a heartbeat thread claims its message again every second (sync) or ten (jobs), so only a dead worker's message
is ever taken over. A sync message past its deadline is dropped (the API has answered 504 already); one that has
killed MAX_DELIVERIES workers is answered E_INTERNAL; one for another kernel is put on that kernel's stream
(Forwarded) and answered there. The message is acknowledged once it is answered or passed on."""

import contextlib
import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from redis import Redis
from redis.exceptions import RedisError, ResponseError

from glyphh_ada import days, protocol
from glyphh_ada.errors import Refusal
from glyphh_ada.protocol import GROUP, SYNC, Message
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.ada")

BLOCK_MS: int = 2000
STALE_CONSUMER_MS: int = 86_400_000  # a consumer gone a day with nothing pending leaves the group
# dispatch answers (data, version) or (data, version, about): `about` the model's Ada version, for the API's headers
Dispatch = Callable[[Message], tuple[Any, ...]]


class Forwarded(Exception):  # noqa: N818: not an error, a message passed on to another kernel's stream
    """Raised by dispatch when it has put the message on another kernel's stream: nothing to answer here."""


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


class Alive:
    """Says this worker is alive, for each stream it reads, now and every ALIVE_EVERY seconds while it runs (busy or
    not), in that stream's sorted set (protocol.alive_key), dropping members silent for ALIVE_FORGET; it takes itself
    out when the worker stops. A Redis that fails is tried again at the next beat."""

    def __init__(self, redis: Redis, streams: list[str], consumer: str, every: float = protocol.ALIVE_EVERY) -> None:
        self.redis, self.consumer, self.every = redis, consumer, every
        self.keys = [protocol.alive_key(s) for s in streams]
        self.stop, self.thread = threading.Event(), threading.Thread(target=self._run, daemon=True)

    def beat(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        pipe = self.redis.pipeline(transaction=False)
        for key in self.keys:
            pipe.zadd(key, {self.consumer: now}).zremrangebyscore(key, "-inf", now - protocol.ALIVE_FORGET)
            pipe.expire(key, protocol.ALIVE_FORGET)
        try:
            pipe.execute()
        except RedisError:
            return False
        return True

    def _run(self) -> None:
        self.beat()
        while not self.stop.wait(self.every):
            self.beat()

    def __enter__(self) -> "Alive":
        self.thread.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop.set()
        self.thread.join()
        with contextlib.suppress(RedisError):
            for key in self.keys:
                self.redis.zrem(key, self.consumer)


class Loop:
    def __init__(
        self, queue: str, redis: Redis, consumer: str, dispatch: Dispatch, streams: list[str] | None = None
    ) -> None:
        self.queue, self.redis, self.consumer, self.dispatch = queue, redis, consumer, dispatch
        self.streams = streams or [protocol.STREAMS[queue]]

    def ensure_group(self) -> None:
        """Each stream and its group, made once; consumers long gone with nothing pending removed."""
        for stream in self.streams:
            try:
                self.redis.xgroup_create(stream, GROUP, id="0", mkstream=True)
            except ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise
            # Upstash answers no consumers at all: nothing is removed there. One without its numbers is kept.
            for c in self.redis.xinfo_consumers(stream, GROUP):
                if c.get("pending", 1) == 0 and c.get("idle", 0) > STALE_CONSUMER_MS:
                    self.redis.xgroup_delconsumer(stream, GROUP, c["name"])

    def alive(self) -> Alive:
        """This worker's beat on each of its streams, for as long as it serves."""
        return Alive(self.redis, self.streams, self.consumer)

    def _next(self) -> tuple[str, str, dict[str, str] | None, bool] | None:
        idle = protocol.CLAIM_IDLE[self.queue]
        for stream in self.streams:
            claimed = self.redis.xautoclaim(stream, GROUP, self.consumer, idle, start_id="0-0", count=1)
            if claimed[1]:
                return stream, claimed[1][0][0], claimed[1][0][1], True
        wanted = dict.fromkeys(self.streams, ">")
        got = self.redis.xreadgroup(GROUP, self.consumer, wanted, count=1, block=BLOCK_MS)  # type: ignore[arg-type]
        return (got[0][0], got[0][1][0][0], got[0][1][0][1], False) if got else None

    def one(self) -> bool:
        """Take and answer one message; False when none came."""
        found = self._next()
        if found is None:
            return False
        stream, message_id, raw, claimed = found
        if raw:
            with Heartbeat(self.redis, stream, self.consumer, message_id, protocol.HEARTBEAT[self.queue]):
                self._answer(Message.of(raw), self._deliveries(stream, message_id) if claimed else 1)
        self.redis.xack(stream, GROUP, message_id)
        return True

    def _deliveries(self, stream: str, message_id: str) -> int:
        pending = self.redis.xpending_range(stream, GROUP, min=message_id, max=message_id, count=1)
        return int(pending[0]["times_delivered"]) if pending else 1

    def _answer(self, msg: Message, deliveries: int) -> None:
        about = fields(op=msg.op, org=msg.org, request=msg.id, deliveries=deliveries)
        if self.queue == SYNC and msg.expired:
            log.warning("dropped past its deadline", extra=about)
            return
        if deliveries > protocol.MAX_DELIVERIES:
            log.error("dropped: it stopped too many workers", extra=about)
            return self._reply(msg, protocol.refused("E_INTERNAL", "This request could not be answered.", 500))
        data: Any = None
        try:
            data, version, *ada = self.dispatch(msg)
            answer = protocol.ok(data, version, *ada)
        except Forwarded:
            return
        except Refusal as r:
            answer = protocol.refused(r.code, r.message, r.status, **r.detail)
        except Exception:  # a crash is the caller's E_INTERNAL; the worker goes on
            log.exception("failed", extra=about)
            answer = protocol.refused("E_INTERNAL", "Something went wrong on our side.", 500, request=msg.id)
        self._reply(msg, answer)
        if msg.op == "decide" and isinstance(data, dict):  # its model's day, once the caller has its answer
            days.decided(self.redis, msg.org, msg.model, data, msg.args.get("output"))

    def _reply(self, msg: Message, answer: str) -> None:
        if self.queue == SYNC:
            key = protocol.reply_key(msg.id)
            self.redis.pipeline().lpush(key, answer).expire(key, protocol.REPLY_TTL).execute()
