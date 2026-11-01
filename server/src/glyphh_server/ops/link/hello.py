"""The first message on a link: the rrotor's `hello`, within 10 seconds, of protocol 2, naming the runtime its token
is. Anything else closes the link with its reason: another protocol (1 included) 4426 (update the rrotor), the rest
4400."""

import json

import anyio
from pydantic import ValidationError
from starlette.websockets import WebSocket

from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import BAD_HELLO, PROTOCOL, UPGRADE, Hello

HELLO_WAIT: float = 10.0


async def next_text(ws: WebSocket) -> str | None:
    """The next frame's text; None once the rrotor has hung up. A binary frame is unreadable: no text."""
    message = await ws.receive()
    if message["type"] == "websocket.disconnect":
        return None
    return message.get("text") or ""


def _json(raw: str) -> object:
    try:
        return json.loads(raw)
    except ValueError:
        return None


async def read_hello(ws: WebSocket, runtime: Runtime) -> Hello | None:
    """The rrotor's hello, or None once the link is closed for the lack of a good one."""
    with anyio.move_on_after(HELLO_WAIT):
        raw = await next_text(ws)
        if raw is None:
            return None
        data = _json(raw)
        if isinstance(data, dict) and data.get("type") == "hello" and data.get("protocol") != PROTOCOL:
            await ws.close(UPGRADE, f"This server speaks protocol {PROTOCOL}. Update the rrotor.")
            return None
        try:
            hello = Hello.model_validate(data)
        except ValidationError:
            await ws.close(BAD_HELLO, "The first message must be hello {protocol, version, mode, runtime_id}.")
            return None
        if hello.runtime_id != runtime.id or hello.mode != runtime.mode:
            await ws.close(BAD_HELLO, "This hello names another runtime than its token.")
            return None
        return hello
    await ws.close(BAD_HELLO, f"Say hello within {HELLO_WAIT:g} seconds.")
    return None
