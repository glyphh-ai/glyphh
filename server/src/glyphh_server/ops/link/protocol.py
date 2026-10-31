"""Protocol 2: JSON messages over the WebSocket, one per frame, each with `type` and `id` (rrotor's
src/rrotord/link/protocol.py). Protocol 2 names a program `program` where protocol 1 said `model`; a hello of any other
protocol is closed 4426 (`upgrade_needed`).

The link carries licensing only: the hello (who the runtime is, the node it is), the welcome (the org's licence key, and
a self-hosted runtime's licence and runtime keys), `keys` when those change, and rrotor's `usage` (each runtime key's
calls, its precedents). rrotor may still send a `result`, an `event` or a `deployed`: the server keeps none of them and
acks each, so rrotor stops owing it. Every message is checked here; anything the models refuse is unreadable, logged and
skipped, and the link stays. `usage` carries `seq`, one rising counter per runtime: the server acks each by its `id`
and applies a `seq` once, so a replay after a reconnect is never doubled."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from glyphh_server.models import MODES
from glyphh_server.ops.license import License
from glyphh_server.ops.nodes import NodeId, Role

PROTOCOL: int = 2  # 1 named a program `model`

# How a link is closed, so the rrotor knows whether to reconnect.
REFUSED: int = 4401  # the runtime token is not valid, or its install was signed out: do not retry with it
BAD_HELLO: int = 4400  # the first message was not a good hello for this runtime
SILENT: int = 4408  # nothing heard for three pings
REPLACED: int = 4409  # a newer link of the same runtime took over
UPGRADE: int = 4426  # a different protocol: update the rrotor
FAILED: int = 1011  # the server could not record a message: reconnect, and replay what is not acked
RESTART: int = 1012  # the server is restarting: reconnect

Id = Annotated[str, Field(min_length=1, max_length=64)]
Name = Annotated[str, Field(min_length=1, max_length=200)]
Seq = Annotated[int, Field(ge=1)]
Mode = Literal[MODES]  # type: ignore[valid-type]


def new_id() -> str:
    return uuid.uuid4().hex


class Message(BaseModel):
    id: Id = Field(default_factory=new_id)


# rrotor → server


class Hello(Message):
    """The link's first message. The programs it says are deployed are the runtime's own business, never kept."""

    type: Literal["hello"]
    protocol: int
    version: Name  # the rrotor's version
    mode: Mode
    runtime_id: uuid.UUID
    node_id: NodeId | None = None  # a standalone node or a cluster's head (rrotor's cluster.md): kept, ops/nodes.py
    cluster_id: uuid.UUID | None = None
    role: Role | None = None


class KeyUse(BaseModel):
    key_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    calls: int = Field(ge=1)
    last_used_at: datetime


class Usage(Message):
    """The runtime keys' calls since the last report, one entry per key that let a request in; and the runtime's
    precedents, its total across its Ada models now, once rrotor has read it."""

    type: Literal["usage"]
    seq: Seq
    keys: list[KeyUse] = []
    precedents: int | None = Field(None, ge=0)


class Passed(Message):
    """A run's result, a program's event or a deployed version: rrotor still sends them, the server keeps none."""

    type: Literal["result", "event", "deployed"]


class Ping(Message):
    type: Literal["ping"] = "ping"


class Pong(Message):
    type: Literal["pong"] = "pong"


class Ack(Message):
    type: Literal["ack"] = "ack"
    of: Id


Inbound = Annotated[Usage | Passed | Ping | Pong | Ack, Field(discriminator="type")]
INBOUND: TypeAdapter[Inbound] = TypeAdapter(Inbound)


# server → rrotor


class Welcome(Message):
    type: Literal["welcome"] = "welcome"
    accepted: bool = True
    licence: License | None = None  # a self-hosted runtime's plan licence: it has no mod to hand one in
    license_key: str | None = None  # the org's newest licence key (ops/license_keys.py), to every runtime
    keys: list[str] | None = None  # a self-hosted runtime's live runtime keys, as SHA-256s: what it checks bearers by


class Keys(Message):
    """The runtime keys changed: the whole live list of their SHA-256s (one revoked is one gone)."""

    type: Literal["keys"] = "keys"
    hashes: list[str]
