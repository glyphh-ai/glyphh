"""A server-sent events client straight on the ASGI app: httpx's ASGI transport waits for a whole body, and a stream
never ends. It reads the frames as they are sent, then hangs up as a browser would."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI

WAIT: float = 5.0


@dataclass
class Stream:
    status: int
    frames: asyncio.Queue[str] = field(default_factory=asyncio.Queue)

    async def frame(self) -> str:
        return await asyncio.wait_for(self.frames.get(), WAIT)

    async def event(self) -> str:
        """The next event, past any heartbeat comment."""
        while (frame := await self.frame()).startswith(":"):
            pass
        return frame


def _scope(path: str, headers: dict[str, str]) -> dict[str, object]:
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("127.0.0.1", 50000),
        "server": ("test", 80),
    }


@asynccontextmanager
async def sse(app: FastAPI, path: str, headers: dict[str, str]) -> AsyncIterator[Stream]:
    started: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    frames: asyncio.Queue[str] = asyncio.Queue()
    gone = asyncio.Event()

    async def receive() -> dict[str, object]:
        await gone.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, object]) -> None:
        if message["type"] == "http.response.start":
            started.set_result(int(message["status"]))  # type: ignore[call-overload]
        elif body := message.get("body"):
            frames.put_nowait(body.decode())  # type: ignore[attr-defined]

    task = asyncio.create_task(app(_scope(path, headers), receive, send))  # type: ignore[arg-type]
    stream = Stream(await asyncio.wait_for(started, WAIT), frames)
    try:
        yield stream
    finally:
        gone.set()
        await asyncio.wait_for(task, WAIT)
