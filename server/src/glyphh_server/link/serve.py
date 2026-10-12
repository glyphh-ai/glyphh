"""One machine's connection: signed in with its own token (in a header, never the URL), every report applied and
passed on, and offline again when it goes. A report that cannot be read is logged and skipped; the connection stays."""

import logging
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.link import record
from glyphh_server.link.hub import Hub
from glyphh_server.link.wire import PROTOCOL, REPORT, Hello, SessionEvent
from glyphh_server.obs.logs import fields
from glyphh_server.ops.auth.secrets import hash_secret

log = logging.getLogger("glyphh.link")
UNAUTHORIZED: int = 4401
UPGRADE: int = 4426


def _token(ws: WebSocket) -> str:
    scheme, _, token = ws.headers.get("authorization", "").partition(" ")
    return token if scheme.lower() == "bearer" else ""


async def _machine(engine: AsyncEngine, token: str) -> uuid.UUID | None:
    if not token:
        return None
    async with engine.begin() as conn:
        found = await record.machine_by_token(conn, hash_secret(token))
    return None if found is None else found[0]


async def serve(ws: WebSocket) -> None:
    engine: AsyncEngine = ws.app.state.engine
    hub: Hub = ws.app.state.hub
    machine = await _machine(engine, _token(ws))
    if machine is None:
        await ws.close(code=UNAUTHORIZED)
        return
    await ws.accept()
    send = ws.send_text  # one object for connected and gone: each `ws.send_text` is a new bound method
    hub.connected(machine, send)
    log.info("machine connected", extra=fields(machine=str(machine)))
    try:
        while await _report(ws, engine, hub, machine, await ws.receive_text()):
            pass
    except WebSocketDisconnect:
        pass
    finally:
        hub.gone(machine, send)
        async with engine.begin() as conn:
            await record.seen(conn, machine, online=False)
        log.info("machine gone", extra=fields(machine=str(machine)))


async def _report(ws: WebSocket, engine: AsyncEngine, hub: Hub, machine: uuid.UUID, raw: str) -> bool:
    """Applies one report; False ends the connection (a machine on a protocol this server does not speak)."""
    try:
        report = REPORT.validate_json(raw)
    except ValidationError as err:
        log.warning("unreadable report", extra=fields(machine=str(machine), error=str(err.errors()[0]["msg"])))
        return True
    if isinstance(report, Hello):
        return await _hello(ws, engine, machine, report)
    if isinstance(report, SessionEvent):
        async with engine.begin() as conn:
            mine = await record.event(conn, machine, report)
        if not mine:
            log.warning("event for a thread not this machine's", extra=fields(machine=str(machine)))
            return True
    log.info("reported", extra=fields(machine=str(machine), type=report.type))
    if report.thread:
        hub.publish(report.thread, report.model_dump(mode="json"))
    return True


async def _hello(ws: WebSocket, engine: AsyncEngine, machine: uuid.UUID, hello: Hello) -> bool:
    if hello.protocol != PROTOCOL:
        log.warning("protocol not spoken", extra=fields(machine=str(machine), protocol=hello.protocol))
        await ws.close(code=UPGRADE, reason=f"this server speaks protocol {PROTOCOL}")
        return False
    async with engine.begin() as conn:
        await record.seen(conn, machine, online=True, version=hello.version)
    return True
