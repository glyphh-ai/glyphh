"""Who is connected and who is watching, in this process: each machine's connection, to send it commands, and each
thread's watchers, to pass its events on. Nothing is kept: an event goes to whoever watches now, and is gone.

One process only for now. With more than one, a machine's connection is on one process and a thread's watcher may
be on another: Redis's publish and subscribe joins them (the architecture, Data), when the server runs more than one."""

import asyncio
import json
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

Send = Callable[[str], Awaitable[None]]
WAITING: int = 256


class Hub:
    def __init__(self) -> None:
        self._machines: dict[uuid.UUID, Send] = {}
        self._watchers: dict[uuid.UUID, set[asyncio.Queue[dict[str, Any] | None]]] = defaultdict(set)

    def connected(self, machine: uuid.UUID, send: Send) -> None:
        self._machines[machine] = send

    def gone(self, machine: uuid.UUID, send: Send) -> None:
        """Forgets the machine, unless a newer connection of the same machine took its place."""
        if self._machines.get(machine) is send:
            del self._machines[machine]

    def online(self, machine: uuid.UUID) -> bool:
        return machine in self._machines

    async def tell(self, machine: uuid.UUID, msg: dict[str, Any]) -> bool:
        """Sends a command to a connected machine; False when it is not connected here."""
        send = self._machines.get(machine)
        if send is None:
            return False
        await send(json.dumps(msg))
        return True

    def publish(self, thread: uuid.UUID, msg: dict[str, Any]) -> None:
        """Passes a thread's event to whoever watches it; a watcher too far behind misses it, never the machine."""
        for queue in self._watchers.get(thread, set()):
            if queue.qsize() < WAITING:
                queue.put_nowait(msg)

    def end(self, thread: uuid.UUID) -> None:
        """Ends every watch of a thread (it was deleted)."""
        for queue in self._watchers.pop(thread, set()):
            queue.put_nowait(None)

    @asynccontextmanager
    async def watch(self, thread: uuid.UUID) -> AsyncIterator[asyncio.Queue[dict[str, Any] | None]]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self._watchers[thread].add(queue)
        try:
            yield queue
        finally:
            self._watchers.get(thread, set()).discard(queue)
