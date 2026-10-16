"""One runtime's link, from its token to its close.

The link is accepted, then refused with a close and its reason when the token is not good (4401). The first message
must be `hello` (ops/link/hello.py): another protocol is closed 4426, anything else 4400. Then the Cloud answers
`welcome`, the runtime is online, and three things run until one ends: reading the rrotor's messages, a ping every 20
seconds (nothing heard for three closes it, 4408), and the hub's relay of what other processes send it. An
unreadable message is logged and skipped; one that cannot be recorded closes the link (1011) and is not acked, so the
rrotor replays it after it reconnects."""

import logging
from dataclasses import dataclass, field
from functools import partial

import anyio
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from starlette.websockets import WebSocket

from glyphh_server.db import tenancy
from glyphh_server.obs.context import bound
from glyphh_server.obs.logs import fields
from glyphh_server.ops.link import inbound
from glyphh_server.ops.link.hello import next_text, read_hello
from glyphh_server.ops.link.hub import Hub, Link
from glyphh_server.ops.link.presence import OFFLINE, ONLINE, Refused, Runtime, mark, runtime_for
from glyphh_server.ops.link.protocol import (
    FAILED,
    INBOUND,
    REFUSED,
    SILENT,
    Ack,
    Deployed,
    Event,
    Inbound,
    Limits,
    Ping,
    Pong,
    Result,
    Welcome,
)
from glyphh_server.ops.routines import Routines

log = logging.getLogger("glyphh.link")

PING_EVERY: float = 20.0
MISSED: int = 3


@dataclass(frozen=True, slots=True)
class Context:
    engine: AsyncEngine
    redis: Redis
    hub: Hub
    routines: Routines
    secrets_key: bytes | None


@dataclass(slots=True)
class Clock:
    heard: float = field(default_factory=anyio.current_time)


async def serve(ws: WebSocket, ctx: Context, token: str | None) -> None:
    await ws.accept()
    try:
        runtime = await runtime_for(ctx.engine, token)
    except Refused as refused:
        await ws.close(REFUSED, str(refused))
        return
    with bound(user=str(runtime.user_id), org=str(runtime.org_id)):
        hello = await read_hello(ws, runtime)
        if hello is None:
            return
        await mark(ctx.engine, runtime, ONLINE, hello.version)
        link = Link(ws, runtime.id)
        log.info("runtime linked", extra=fields(runtime=str(runtime.id), mode=runtime.mode, version=hello.version))
        try:
            await _run(ctx, runtime, link)
        finally:
            ctx.hub.detach(link)
            if not link.replaced:  # else a newer link of this runtime is online now
                with anyio.CancelScope(shield=True):
                    await mark(ctx.engine, runtime, OFFLINE)
            log.info("runtime unlinked", extra=fields(runtime=str(runtime.id), replaced=link.replaced))


async def _run(ctx: Context, runtime: Runtime, link: Link) -> None:
    async with ctx.hub.listening(link) as pubsub:
        await ctx.hub.attach(link)
        limits = Limits(runtime_hours=runtime.runtime_hours if runtime.mode == "hosted" else None)
        await link.send(Welcome(limits=limits).model_dump(mode="json"))
        clock = Clock()
        async with anyio.create_task_group() as jobs:

            async def until_done(job: partial[object]) -> None:
                await job()
                jobs.cancel_scope.cancel()

            jobs.start_soon(until_done, partial(_read, ctx, runtime, link, clock))
            jobs.start_soon(until_done, partial(_heartbeat, link, clock))
            jobs.start_soon(until_done, partial(ctx.hub.relay, link, pubsub))


async def _heartbeat(link: Link, clock: Clock) -> None:
    every = PING_EVERY
    while True:
        await anyio.sleep(every)
        if anyio.current_time() - clock.heard > every * MISSED:
            await link.close(SILENT, f"Nothing heard for {every * MISSED:g} seconds.")
            return
        if not await link.send(Ping().model_dump()):
            return


async def _read(ctx: Context, runtime: Runtime, link: Link, clock: Clock) -> None:
    while (raw := await next_text(link.ws)) is not None:
        clock.heard = anyio.current_time()
        try:
            message = INBOUND.validate_json(raw)
        except ValidationError as err:
            log.warning(
                "unreadable message skipped",
                extra=fields(runtime=str(runtime.id), error=err.errors(include_input=False, include_url=False)[:3]),
            )
            continue
        if not await _apply(ctx, runtime, link, message):
            return


async def _apply(ctx: Context, runtime: Runtime, link: Link, message: Inbound) -> bool:
    """Answer or record one message; False once the link is closed because it could not be recorded."""
    if isinstance(message, Ping | Pong | Ack):
        if isinstance(message, Ping):
            await link.send(Pong().model_dump())
        return True
    try:
        async with ctx.engine.begin() as conn:
            await tenancy.enter(conn, runtime.org_id)
            await _record(conn, ctx, runtime, message)
    except Exception:
        log.exception("message not recorded", extra=fields(runtime=str(runtime.id), type=message.type))
        await link.close(FAILED, "That message could not be recorded. Reconnect and replay it.")
        return False
    await link.send(Ack(of=message.id).model_dump())
    return True


async def _record(conn: AsyncConnection, ctx: Context, runtime: Runtime, message: Result | Deployed | Event) -> None:
    if isinstance(message, Deployed):
        await inbound.apply_deployed(conn, runtime, message)
    elif not await inbound.first_time(conn, runtime, message.seq):
        log.info("replay skipped", extra=fields(runtime=str(runtime.id), seq=message.seq))
    elif isinstance(message, Result):
        await inbound.apply_result(conn, ctx.redis, runtime, message)
    else:
        await inbound.apply_event(conn, ctx.routines, ctx.secrets_key, runtime, message)
