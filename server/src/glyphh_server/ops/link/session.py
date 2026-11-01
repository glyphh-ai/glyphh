"""One runtime's link, from its token to its close.

The link is accepted, then refused with a close and its reason when the token is not good (4401). The first message
must be `hello` (ops/link/hello.py): another protocol is closed 4426, anything else 4400. Then the server answers
`welcome`, the runtime is online, and three things run until one ends: reading the rrotor's messages, a ping every 20
seconds (nothing heard for three closes it, 4408), and the hub's relay of what other processes send it (`keys`). An
unreadable message is logged and skipped; one that cannot be recorded closes the link (1011) and is not acked, so the
rrotor replays it after it reconnects."""

import logging
from dataclasses import dataclass, field
from functools import partial

import anyio
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.websockets import WebSocket

from glyphh_server.db import tenancy
from glyphh_server.obs.context import bound
from glyphh_server.obs.logs import fields
from glyphh_server.ops import catalogue as artifacts
from glyphh_server.ops import license_keys
from glyphh_server.ops.license import GRACE_DAYS, LINK, Stamp, sign_license
from glyphh_server.ops.link import inbound, reports
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
    Inbound,
    Ping,
    Pong,
    Usage,
    Welcome,
)
from glyphh_server.ops.runtime_keys import hashes_for

log = logging.getLogger("glyphh.link")

PING_EVERY: float = 20.0
MISSED: int = 3


@dataclass(frozen=True, slots=True)
class Context:
    engine: AsyncEngine
    hub: Hub
    signing_key: Ed25519PrivateKey | None = None  # signs the licence a self-hosted runtime's welcome carries


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
        await inbound.record_hello(ctx.engine, runtime, hello)
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
        await link.send((await _welcome(ctx, runtime)).model_dump(mode="json"))
        clock = Clock()
        async with anyio.create_task_group() as jobs:

            async def until_done(job: partial[object]) -> None:
                await job()
                jobs.cancel_scope.cancel()

            jobs.start_soon(until_done, partial(_read, ctx, runtime, link, clock))
            jobs.start_soon(until_done, partial(_heartbeat, link, clock))
            jobs.start_soon(until_done, partial(ctx.hub.relay, link, pubsub))


async def _welcome(ctx: Context, runtime: Runtime) -> Welcome:
    """Every runtime's welcome carries the org's newest licence key (null: none). A local runtime's has no licence
    (its mod hands one in); a self-hosted one's carries its runtime keys and its licence, with the licence's grace."""
    async with ctx.engine.begin() as conn:
        await tenancy.enter(conn, runtime.org_id)
        license_key = await license_keys.newest(conn, runtime.org_id)
        catalogue = await artifacts.for_runtime(conn, runtime.id)
        reviewers = await artifacts.reviewer_groups(conn, runtime.org_id)
        if runtime.mode == "local":
            return Welcome(license_key=license_key, artifacts=catalogue, reviewers=reviewers)
        keys, licence = await hashes_for(conn, runtime.id), None
        if ctx.signing_key is not None:
            stamp = Stamp(runtime.id, LINK, GRACE_DAYS)
            licence = await sign_license(conn, ctx.signing_key, runtime.user_id, runtime.org_id, None, stamp)
    return Welcome(licence=licence, license_key=license_key, keys=keys, artifacts=catalogue, reviewers=reviewers)


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
    """Answer or record one message; False once the link is closed because it could not be recorded. A result or an
    event (Passed) is acked and kept nowhere; a deployed app makes its catalogue row."""
    if isinstance(message, Ping | Pong | Ack):
        if isinstance(message, Ping):
            await link.send(Pong().model_dump())
        return True
    if isinstance(message, Usage | Deployed):
        try:
            await _record(ctx, runtime, message)
        except Exception:
            log.exception("message not recorded", extra=fields(runtime=str(runtime.id), type=message.type))
            await link.close(FAILED, "That message could not be recorded. Reconnect and replay it.")
            return False
    await link.send(Ack(of=message.id).model_dump())
    return True


async def _record(ctx: Context, runtime: Runtime, message: Usage | Deployed) -> None:
    async with ctx.engine.begin() as conn:
        await tenancy.enter(conn, runtime.org_id)
        if isinstance(message, Deployed):
            await artifacts.catalogue_deployed(conn, runtime, message)
        elif await inbound.first_time(conn, runtime, message.seq):
            await reports.apply_usage(conn, runtime, message)
        else:
            log.info("replay skipped", extra=fields(runtime=str(runtime.id), seq=message.seq))
