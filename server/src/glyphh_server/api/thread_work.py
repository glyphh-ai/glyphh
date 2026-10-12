"""Working a thread through its machine: start one, say more, stop it, and watch it live. Watching streams each
event the machine reports as it comes (Server-Sent Events), kept nowhere."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.errors import Unauthorized
from glyphh_server.link.hub import Hub
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.tokens import principal_for
from glyphh_server.ops.threads.run import Say, ThreadStart, say, start_thread, stop
from glyphh_server.ops.threads.shape import ThreadRow, my_thread

router = APIRouter(prefix="/v1", tags=["threads"])
PING_SECONDS: float = 15


@router.post("/machines/{machine_id}/threads", operation_id="startThread", status_code=201)
async def start(machine_id: uuid.UUID, body: ThreadStart, caller: Caller, request: Request) -> ThreadRow:
    """Start a thread on one of my machines: one super power on its own, or a crew Glyphh leads."""
    return await start_thread(request.app.state.engine, caller, request.app.state.hub, machine_id, body)


@router.post("/threads/{thread_id}/say", operation_id="sayToThread", status_code=204)
async def say_more(thread_id: uuid.UUID, body: Say, caller: Caller, conn: Conn, request: Request) -> Response:
    """Say more in a thread; its machine must be connected."""
    await say(conn, caller, request.app.state.hub, thread_id, body.text)
    return Response(status_code=204)


@router.post("/threads/{thread_id}/stop", operation_id="stopThread", status_code=204)
async def stop_one(thread_id: uuid.UUID, caller: Caller, conn: Conn, request: Request) -> Response:
    """Stop the work in a thread; its record stays."""
    await stop(conn, caller, request.app.state.hub, thread_id)
    return Response(status_code=204)


async def watcher(request: Request) -> Principal:
    """Who is watching, checked on a connection of its own, so a long watch holds no transaction open."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized("Sign in to Glyphh: send your access token as a Bearer token.")
    async with request.app.state.engine.connect() as conn:
        return await principal_for(conn, token)


@router.get("/threads/{thread_id}/events", operation_id="watchThread", response_class=StreamingResponse)
async def watch(
    thread_id: uuid.UUID, who: Annotated[Principal, Depends(watcher)], request: Request
) -> StreamingResponse:
    """A thread's events as its machine reports them, live: one Server-Sent Event each, numbered within the thread."""
    async with request.app.state.engine.connect() as conn:
        await my_thread(conn, who, thread_id)
    headers = {"cache-control": "no-store", "x-accel-buffering": "no"}
    return StreamingResponse(events(request.app.state.hub, thread_id), media_type="text/event-stream", headers=headers)


async def events(hub: Hub, thread: uuid.UUID) -> AsyncIterator[str]:
    async with hub.watch(thread) as queue:
        yield ": watching\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), PING_SECONDS)
            except TimeoutError:
                yield ": ping\n\n"
                continue
            if msg is None:
                return
            seq = f"id: {msg['seq']}\n" if "seq" in msg else ""
            yield f"{seq}event: {msg['type']}\ndata: {json.dumps(msg)}\n\n"
