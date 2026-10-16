"""The hub: which server process holds which runtime's link.

Each process keeps its own links in memory, one per runtime. A message for a runtime held here goes straight down
its link; otherwise it is published on the runtime's Redis channel, `runtime:{id}`, which the process holding that
link listens on, and nobody hearing it means the runtime is not connected. A newer link of the same runtime takes
over: here at once, elsewhere by a `takeover` on the channel, and the older link is closed (4409). Frames never cross
processes: they stay with the process holding the link, best effort."""

import json
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from typing import Any

import anyio
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from starlette.websockets import WebSocket, WebSocketDisconnect

from glyphh_server.db.signals import publish
from glyphh_server.obs.logs import fields
from glyphh_server.ops.link.protocol import REPLACED, RESTART

log = logging.getLogger("glyphh.link")


def channel(runtime_id: uuid.UUID) -> str:
    return f"runtime:{runtime_id}"


class Link:
    """One rrotor's open WebSocket. Sends are taken one at a time; a send to a link already gone answers False."""

    def __init__(self, ws: WebSocket, runtime_id: uuid.UUID) -> None:
        self.id, self.ws, self.runtime_id = uuid.uuid4(), ws, runtime_id
        self.replaced = False
        self._sending = anyio.Lock()

    async def send(self, message: dict[str, Any]) -> bool:
        async with self._sending:
            try:
                await self.ws.send_text(json.dumps(message, separators=(",", ":")))
            except (RuntimeError, WebSocketDisconnect):
                return False
        return True

    async def close(self, code: int, reason: str) -> None:
        with suppress(RuntimeError, WebSocketDisconnect):
            await self.ws.close(code, reason)

    async def replace(self) -> None:
        self.replaced = True
        await self.close(REPLACED, "A newer link of this runtime took over.")


Waker = Callable[[uuid.UUID], Awaitable[None]]


class Hub:
    def __init__(self, redis: Redis, waker: Waker | None = None) -> None:
        self.redis = redis
        self.links: dict[uuid.UUID, Link] = {}
        self.waker = waker  # starts a stopped hosted runtime's machine; None where hosting is off

    async def attach(self, link: Link) -> None:
        """This process now holds the runtime's link; an older one, here or on another process, is closed. Said once
        the link is listening on its channel, which hears its own takeover and passes over it."""
        older = self.links.get(link.runtime_id)
        self.links[link.runtime_id] = link
        if older is not None:
            await older.replace()
        await publish(self.redis, channel(link.runtime_id), "takeover", {"link": str(link.id)})

    def detach(self, link: Link) -> None:
        if self.links.get(link.runtime_id) is link:
            del self.links[link.runtime_id]

    async def deliver(self, runtime_id: uuid.UUID, message: dict[str, Any]) -> bool:
        """Down the runtime's link, wherever it is held. False: no process holds it."""
        link = self.links.get(runtime_id)
        if link is not None:
            return await link.send(message)
        return await publish(self.redis, channel(runtime_id), "send", message) > 0

    @asynccontextmanager
    async def listening(self, link: Link) -> AsyncIterator[PubSub]:
        """Subscribed to the runtime's channel for the link's life; the Redis connection goes back after."""
        pubsub = self.redis.pubsub()
        try:
            await pubsub.subscribe(channel(link.runtime_id))
            yield pubsub
        finally:
            with anyio.CancelScope(shield=True):
                await pubsub.aclose()

    async def relay(self, link: Link, pubsub: PubSub) -> None:
        """What other processes publish for this runtime goes down its link. Ends when another link takes over."""
        while True:
            heard = await pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
            if heard is None:
                continue
            signal = json.loads(heard["data"])
            if signal["event"] == "send":
                await link.send(signal["data"])
            elif signal["data"]["link"] != str(link.id):
                log.info("link taken over", extra=fields(runtime=str(link.runtime_id)))
                await link.replace()
                return

    async def close_all(self) -> None:
        """The server is stopping: every link here is closed so its rrotor reconnects to another process."""
        for link in list(self.links.values()):
            await link.close(RESTART, "The server is restarting. Reconnect.")
