"""A rrotor on the link, for the tests: runtimes made straight in the database, a server reached by a real WebSocket
in-process, a hello said, and a process holding a runtime's link stood in for on its Redis channel."""

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx_ws import AsyncWebSocketSession, WebSocketDisconnect, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from redis.asyncio import Redis
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.db import tenancy
from glyphh_server.models import Rrotor
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.auth.secrets import hash_secret, make_secret
from glyphh_server.ops.link.hub import channel
from glyphh_server.ops.runtimes import issue_local
from tests.conftest import PROVIDER_SETTINGS
from tests.db.helpers import Person
from tests.fakes import fake_http

WAIT: float = 5.0


@dataclass(frozen=True)
class Rt:
    id: uuid.UUID
    token: str
    mode: str


@dataclass(frozen=True)
class Server:
    app: FastAPI
    http: httpx.AsyncClient  # HTTP and WebSocket, in-process


def principal(who: Person) -> Principal:
    return Principal(user_id=who.user_id, org_id=who.org_id, role="admin", install_id=who.install_id)


async def local_runtime(engine: AsyncEngine, who: Person) -> Rt:
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        made = await issue_local(conn, principal(who))
    return Rt(made.runtime_id, made.token, "local")


async def self_runtime(engine: AsyncEngine, who: Person, public_url: str = "https://rrotor.acme.test") -> Rt:
    token = make_secret()
    async with engine.begin() as conn:
        values = {"user_id": who.user_id, "mode": "self", "name": "Acme", "public_url": public_url, "state": "stopped"}
        made = insert(Rrotor).values(**values, token_hash=hash_secret(token)).returning(Rrotor.id)
        runtime_id = (await conn.execute(made)).scalar_one()
    return Rt(runtime_id, token, "self")


async def runtime_row(engine: AsyncEngine, runtime_id: uuid.UUID):  # type: ignore[no-untyped-def]
    async with engine.connect() as conn:
        return (await conn.execute(select(Rrotor).where(Rrotor.id == runtime_id))).one()


@asynccontextmanager
async def server() -> AsyncIterator[Server]:
    """One server process: its own app, hub and Redis client, on the one Redis and database."""
    app = create_app(PROVIDER_SETTINGS, http=fake_http())
    async with LifespanManager(app):
        transport = ASGIWebSocketTransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            yield Server(app, http)


def hello(rt: Rt, **over: Any) -> dict[str, Any]:
    said = {"type": "hello", "id": "h1", "protocol": 3, "version": "1.2.3", "mode": rt.mode, "runtime_id": str(rt.id)}
    return {**said, "deployed": [], **over}


@asynccontextmanager
async def connect(srv: Server, token: str | None) -> AsyncIterator[AsyncWebSocketSession]:
    headers = {"authorization": f"Bearer {token}"} if token is not None else {}
    async with aconnect_ws("http://test/v1/runtime/link", srv.http, headers=headers) as ws:
        yield ws


@asynccontextmanager
async def linked(srv: Server, rt: Rt) -> AsyncIterator[AsyncWebSocketSession]:
    """A rrotor that said hello and was welcomed."""
    async with connect(srv, rt.token) as ws:
        await ws.send_json(hello(rt))
        welcome = await ws.receive_json(timeout=WAIT)
        assert welcome["type"] == "welcome" and welcome["accepted"] is True, welcome
        yield ws


async def receive(ws: AsyncWebSocketSession, kind: str) -> dict[str, Any]:
    """The next message of this type, past the pings the server sends."""
    while (message := await ws.receive_json(timeout=WAIT))["type"] != kind:
        assert message["type"] == "ping", message
    return message


@asynccontextmanager
async def holding(redis: Redis, runtime_id: uuid.UUID) -> AsyncIterator[Any]:
    """Stand in for a server process holding this runtime's link: what is sent to it, read from its channel."""
    async with redis.pubsub() as pubsub:
        await pubsub.subscribe(channel(runtime_id))
        await pubsub.get_message(timeout=WAIT)  # the subscription itself

        async def sent() -> dict[str, Any]:
            heard = await pubsub.get_message(ignore_subscribe_messages=True, timeout=WAIT)
            assert heard is not None, "nothing was sent"
            signal = json.loads(heard["data"])
            assert signal["event"] == "send"
            return signal["data"]

        yield sent


async def closed(ws: AsyncWebSocketSession) -> tuple[int, str]:
    """How the server closed the link: its code and reason, past whatever it sent before."""
    try:
        while True:
            await ws.receive(timeout=WAIT)
    except WebSocketDisconnect as gone:
        return gone.code, gone.reason
