"""Protocol 2: JSON messages over the WebSocket, one per frame, each with `type` and `id` (rrotor's
src/rrotord/link/protocol.py). Protocol 2 names a program `program` where protocol 1 said `model`; a hello of any other
protocol is closed 4426 (`upgrade_needed`).

The link carries licensing, and the catalogue of apps: the hello (who the runtime is, the node it is), the welcome
(the org's licence key, a self-hosted runtime's licence and runtime keys, the runtime's artifacts and the org's
reviewer groups), `keys` when those change, `artifact` after each review (docs/specs/artifacts.md), and rrotor's
`usage` (each runtime key's calls, its precedents) and `deployed` (an app's makes its catalogue row). rrotor may still
send a `result` or an `event`: the server keeps neither and acks each, so rrotor stops owing it. Every message is
checked here; anything the models refuse is unreadable, logged and skipped, and the link stays. `usage` carries
`seq`, one rising counter per runtime: the server acks each by its `id` and applies a `seq` once, so a replay after
a reconnect is never doubled."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

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
    """A run's result or a program's event: rrotor still sends them, the server keeps none."""

    type: Literal["result", "event"]


class Deployed(Message):
    """A version deployed on the rrotor, with its manifest: an app's (`kind` app) makes or updates the catalogue row
    (docs/specs/artifacts.md, 3.2), submitted by the Glyphh subject `by` names; any other deploy is kept nowhere."""

    type: Literal["deployed"]
    program: Name
    version: int = Field(ge=1)
    commit_sha: Annotated[str, Field(min_length=1, max_length=64)]
    repo: str | None = None
    manifest: dict[str, Any] | None = None
    by: str | None = None


class Ping(Message):
    type: Literal["ping"] = "ping"


class Pong(Message):
    type: Literal["pong"] = "pong"


class Ack(Message):
    type: Literal["ack"] = "ack"
    of: Id


Inbound = Annotated[Usage | Passed | Deployed | Ping | Pong | Ack, Field(discriminator="type")]
INBOUND: TypeAdapter[Inbound] = TypeAdapter(Inbound)


class ArtifactState(BaseModel):
    """An app's standing in the catalogue, as the rrotor is told it: in the welcome (every row of the runtime) and
    as an `artifact` message after each review."""

    type: Literal["artifact"] = "artifact"
    id: Id = Field(default_factory=new_id)
    program: Name
    version: int
    state: Literal["draft", "approved", "rejected", "retired"]
    roles: list[str] = []


# server → rrotor


class Welcome(Message):
    type: Literal["welcome"] = "welcome"
    accepted: bool = True
    licence: License | None = None  # a self-hosted runtime's plan licence: it has no mod to hand one in
    license_key: str | None = None  # the org's newest licence key (ops/license_keys.py), to every runtime
    keys: list[str] | None = None  # a self-hosted runtime's live runtime keys, as SHA-256s: what it checks bearers by
    artifacts: list[ArtifactState] = []  # the catalogue's rows for this runtime (docs/specs/artifacts.md, 3.4)
    reviewers: list[str] = []  # the org's reviewer groups: who may open a draft to review it


class Keys(Message):
    """The runtime keys changed: the whole live list of their SHA-256s (one revoked is one gone)."""

    type: Literal["keys"] = "keys"
    hashes: list[str]
