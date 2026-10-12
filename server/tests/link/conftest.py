import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
from asgi_lifespan import LifespanManager
from httpx_ws.transport import ASGIWebSocketTransport
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.models import Machine
from glyphh_server.ops.auth import tokens
from glyphh_server.ops.auth.secrets import hash_secret
from tests.conftest import SETTINGS
from tests.db.helpers import make_machine, make_org, make_user


@asynccontextmanager
async def live() -> AsyncIterator[httpx.AsyncClient]:
    """The app, answering both HTTP and the machine link's WebSocket. Opened inside each test, not as a fixture:
    the WebSocket transport must close in the task that opened it."""
    app = create_app(SETTINGS)
    transport = ASGIWebSocketTransport(app=app)
    async with LifespanManager(app), httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        client.app = app  # type: ignore[attr-defined]
        yield client


class Member:
    def __init__(self, org: uuid.UUID, user: uuid.UUID, auth: dict[str, str]) -> None:
        self.org, self.user, self.auth = org, user, auth


async def member(engine: AsyncEngine, email: str) -> Member:
    org = await make_org(engine, f"Link of {email}")
    user = await make_user(engine, org, email, "org_admin")
    async with engine.begin() as conn:
        token = (await tokens.issue(conn, user, org)).access_token
    return Member(org, user, {"authorization": f"Bearer {token}"})


async def machine(engine: AsyncEngine, who: Member, name: str = "studio-mac") -> tuple[uuid.UUID, str]:
    """A machine of theirs, offline until it links, and its token."""
    machine_id = await make_machine(engine, who.org, who.user, name, online=False)
    token = f"machine-{uuid.uuid4()}"
    async with engine.begin() as conn:
        await conn.execute(update(Machine).where(Machine.id == machine_id).values(token_hash=hash_secret(token)))
    return machine_id, token


async def until(check: Callable[[], Awaitable[Any]], seconds: float = 3) -> Any:
    """Waits for what the server does after a message arrives."""
    for _ in range(int(seconds / 0.02)):
        found = await check()
        if found:
            return found
        await asyncio.sleep(0.02)
    raise AssertionError("it never happened")


def event(thread: uuid.UUID, seq: int, ev: dict[str, Any], sp: uuid.UUID | None = None) -> str:
    msg = {
        "type": "session.event",
        "session": str(thread),
        "thread": str(thread),
        "seq": seq,
        "at": "2026-10-12T12:00:00Z",
        "event": ev,
    }
    if sp:
        msg["super_power"] = str(sp)
    return json.dumps(msg)
