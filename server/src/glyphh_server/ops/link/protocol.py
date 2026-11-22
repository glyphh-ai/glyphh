"""Protocol 3: JSON messages over the WebSocket, one per frame, each with `type` and `id` (rrotor's
src/rrotord/link/protocol.py). Protocol 3 names the catalogue's messages `app` and `apps` where protocol 2 said
`artifact` and `artifacts`; protocol 2 named a program `program` where protocol 1 said `model`. A hello of protocol 2
or 3 is accepted (ACCEPTED), and the catalogue's messages go down that link in the names its protocol knows: NAMES is
the one place the two differ, read by `for_protocol`, and nothing else branches on it. A hello of any other protocol
is closed 4426 (`upgrade_needed`). The protocol 2 names leave once no rrotor of 0.2.0 is heard any more.

The link carries licensing, the catalogue of apps and Glyphh's own programs' runs: the hello, the welcome (the org's
licence key, a self-hosted runtime's licence and keys, its apps, the org's reviewer groups), `keys`, `app` after each
review (docs/specs/apps.md), rrotor's `usage` and `deployed`; and `call`, `continue`, `cancel` down for a bot's run or a
project's step on the rrotor (glyphh_bot, glyphh_swarm: docs/specs/bots.md, 9), each answered by numbered `result`s up
(ops/bots/remote.py keeps them). An `event` is acked and kept nowhere. Every message is checked here; anything the
models refuse is unreadable, logged and skipped, and the link stays. `usage` and `result` carry `seq`, one rising
counter per runtime: each is acked by its `id` and applied once, so a replay after a reconnect is never doubled."""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from glyphh_server.models import MODES
from glyphh_server.ops.license import License
from glyphh_server.ops.nodes import NodeId, Role

PROTOCOL: int = 3  # 2 said artifact for an app; 1 named a program `model`
ACCEPTED: tuple[int, ...] = (2, 3)  # 2: a 0.2.0 rrotor, told the catalogue in its own names
NAMES: dict[int, tuple[str, str]] = {2: ("artifact", "artifacts"), 3: ("app", "apps")}  # one app, the welcome's list

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

    def for_protocol(self, protocol: int) -> dict[str, Any]:
        """The frame as a rrotor of this protocol reads it: the same for every message but the catalogue's."""
        return self.model_dump(mode="json")


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
    """A program's event: rrotor still sends them, the server keeps none."""

    type: Literal["event"]


class Ran(Message):
    """A Result of a run the server called (`{status, data, step, prompt}`), numbered."""

    type: Literal["result"]
    seq: Seq
    run_id: uuid.UUID
    result: dict[str, Any]
    seconds: int = 0


class Deployed(Message):
    """A version deployed on the rrotor, with its manifest: an app's (`kind` app) makes or updates the catalogue row
    (docs/specs/apps.md, 3.2), submitted by the Glyphh subject `by` names; any other deploy is kept nowhere."""

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


Inbound = Annotated[Usage | Ran | Passed | Deployed | Ping | Pong | Ack, Field(discriminator="type")]
INBOUND: TypeAdapter[Inbound] = TypeAdapter(Inbound)


# server → rrotor


class AppState(Message):
    """An app's standing in the catalogue, as the rrotor is told it: in the welcome (every row of the runtime) and
    as an `app` message after each review. A protocol 2 rrotor reads it as `artifact`."""

    type: Literal["app"] = "app"
    program: Name
    version: int
    state: Literal["draft", "approved", "rejected", "retired"]
    roles: list[str] = []

    def for_protocol(self, protocol: int) -> dict[str, Any]:
        return {**super().for_protocol(protocol), "type": NAMES[protocol][0]}


class Welcome(Message):
    type: Literal["welcome"] = "welcome"
    accepted: bool = True
    licence: License | None = None  # a self-hosted runtime's plan licence: it has no mod to hand one in
    license_key: str | None = None  # the org's newest licence key (ops/license_keys.py), to every runtime
    keys: list[str] | None = None  # a self-hosted runtime's live runtime keys, as SHA-256s: what it checks bearers by
    apps: list[AppState] = []  # the catalogue's rows for this runtime (docs/specs/apps.md, 3.4)
    reviewers: list[str] = []  # the org's reviewer groups: who may open a draft to review it

    def for_protocol(self, protocol: int) -> dict[str, Any]:
        """The welcome with its list of apps under the name this protocol gives it, each app in its name too."""
        frame = self.model_dump(mode="json", exclude={"apps"})
        frame[NAMES[protocol][1]] = [app.for_protocol(protocol) for app in self.apps]
        return frame


class Keys(Message):
    """The runtime keys changed: the whole live list of their SHA-256s (one revoked is one gone)."""

    type: Literal["keys"] = "keys"
    hashes: list[str]


class Call(Message):
    """A run of one of Glyphh's programs on the rrotor (version null: its active one)."""

    type: Literal["call"] = "call"
    run_id: uuid.UUID
    program: Name
    version: int | None = None
    function: Name
    inputs: dict[str, Any]
    caller: Literal["routine"] = "routine"


class Continue(Message):
    type: Literal["continue"] = "continue"
    run_id: uuid.UUID
    answer: Any = None


class Cancel(Message):
    type: Literal["cancel"] = "cancel"
    run_id: uuid.UUID


# What one process publishes for a link another holds (ops/link/hub.py), always in protocol 3's names.
Outbound = Annotated[AppState | Keys | Call | Continue | Cancel, Field(discriminator="type")]
OUTBOUND: TypeAdapter[Outbound] = TypeAdapter(Outbound)
