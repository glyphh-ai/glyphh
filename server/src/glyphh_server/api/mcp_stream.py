"""A connector call answered as a stream (Streamable HTTP's SSE response): for a tool that follows something as it
goes (registry.STREAMED: run_program), when the client accepts text/event-stream and gave a progressToken, each
progress the tool makes is sent as a notifications/progress message the moment it is made, then the call's answer as
the last message. Any other call is answered with one JSON object, as before."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace
from typing import Any

from fastapi import Request
from starlette.responses import Response, StreamingResponse

from glyphh_server.mcp import protocol
from glyphh_server.mcp.tools import registry
from glyphh_server.mcp.tools.base import Context

log = logging.getLogger("glyphh.mcp")
INTERNAL_ERROR: int = -32603
Respond = Callable[[Context, protocol.Call], Awaitable[Response]]


def token(request: Request, call: protocol.Call) -> str | int | None:
    """The progress token of a call to be streamed (None: answer it as one JSON object)."""
    if call.method != "tools/call" or registry.named(call.params) not in registry.STREAMED:
        return None
    if "text/event-stream" not in request.headers.get("accept", ""):
        return None
    given = (call.params.get("_meta") or {}).get("progressToken")
    return given if isinstance(given, (str, int)) and not isinstance(given, bool) else None


def _sse(message: dict[str, Any]) -> str:
    return f"event: message\ndata: {json.dumps(message, default=str)}\n\n"


def stream(ctx: Context, call: protocol.Call, given: str | int, respond: Respond) -> StreamingResponse:
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    made = 0

    async def progress(message: str) -> None:
        nonlocal made
        made += 1
        params = {"progressToken": given, "progress": made, "message": message}
        await queue.put({"jsonrpc": "2.0", "method": "notifications/progress", "params": params})

    async def answered() -> None:
        try:
            response = await respond(replace(ctx, progress=progress), call)
            await queue.put(json.loads(bytes(response.body)))
        except Exception:
            log.exception("a streamed connector call failed")
            err = protocol.RpcError(INTERNAL_ERROR, "The call failed.")
            err.id = call.id
            await queue.put(protocol.failure(err))
        finally:
            await queue.put(None)

    async def messages() -> AsyncIterator[str]:
        task = asyncio.create_task(answered())
        try:
            while (message := await queue.get()) is not None:
                yield _sse(message)
        finally:
            task.cancel()

    return StreamingResponse(messages(), media_type="text/event-stream", headers={"cache-control": "no-cache"})
