"""Protocol 1: JSON messages over the WebSocket, one per frame, each with `type` and `id` (rrotor docs, section 6).

Every message is checked here; anything the models refuse is unreadable, logged and skipped, and the link stays.
Results and events carry `seq`, one rising counter per runtime: the Cloud acks each by its `id` and applies a `seq`
once, so a replay after a reconnect is never doubled."""

import uuid
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from glyphh_server.models import CALLERS, MODES

PROTOCOL: int = 1

# How a link is closed, so the rrotor knows whether to reconnect.
REFUSED: int = 4401  # the runtime token is not valid, or its install was signed out: do not retry with it
BAD_HELLO: int = 4400  # the first message was not a good hello for this runtime
SILENT: int = 4408  # nothing heard for three pings
REPLACED: int = 4409  # a newer link of the same runtime took over
UPGRADE: int = 4426  # a different protocol: update the rrotor
FAILED: int = 1011  # the Cloud could not record a message: reconnect, and replay what is not acked
RESTART: int = 1012  # the server is restarting: reconnect

RUNNING: str = "running"
WAITING: frozenset[str] = frozenset({"needs_input", "needs_approval"})
FINAL: frozenset[str] = frozenset({"done", "failed", "expired", "cancelled"})

Id = Annotated[str, Field(min_length=1, max_length=64)]
Name = Annotated[str, Field(min_length=1, max_length=200)]
Seq = Annotated[int, Field(ge=1)]
Sha = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
Mode = Literal[MODES]  # type: ignore[valid-type]
Caller = Literal[CALLERS]  # type: ignore[valid-type]


def new_id() -> str:
    return uuid.uuid4().hex


class Message(BaseModel):
    id: Id = Field(default_factory=new_id)


# rrotor → Cloud


class Version(BaseModel):
    program: Name
    version: int = Field(ge=1)
    commit_sha: Sha


class Hello(Message):
    type: Literal["hello"]
    protocol: int
    version: Name  # the rrotor image's version
    mode: Mode
    runtime_id: uuid.UUID
    deployed: list[Version] = []


class Outcome(BaseModel):
    """A run's `Result`; `expired` and `cancelled` end a run that waited too long or was cancelled (5.4)."""

    status: Literal["done", "needs_input", "needs_approval", "failed", "expired", "cancelled"]
    data: Any = None
    step: Name | None = None
    prompt: str | None = None

    @model_validator(mode="after")
    def _approval_names_its_step(self) -> Self:
        if self.status == "needs_approval" and not (self.step and self.prompt):
            raise ValueError("needs_approval carries the step and its prompt")
        return self


class Result(Message):
    type: Literal["result"]
    seq: Seq
    run_id: uuid.UUID
    result: Outcome
    seconds: int = Field(ge=0)


class Deployed(Version, Message):
    type: Literal["deployed"]


class Event(Message):
    type: Literal["event"]
    seq: Seq
    program: Name
    kind: Name
    data: Any = None
    trigger: uuid.UUID | None = None  # the routine trigger to fire, one of the program owner's


class Ping(Message):
    type: Literal["ping"] = "ping"


class Pong(Message):
    type: Literal["pong"] = "pong"


class Ack(Message):
    type: Literal["ack"] = "ack"
    of: Id


Inbound = Annotated[Result | Deployed | Event | Ping | Pong | Ack, Field(discriminator="type")]
INBOUND: TypeAdapter[Inbound] = TypeAdapter(Inbound)


# Cloud → rrotor


class Limits(BaseModel):
    runtime_hours: int | None  # the plan's hosted hours a month; a local runtime's are the computer's own (null)


class Welcome(Message):
    type: Literal["welcome"] = "welcome"
    accepted: bool = True
    limits: Limits


class Call(Message):
    type: Literal["call"] = "call"
    run_id: uuid.UUID
    program: Name
    version: int
    function: Name
    inputs: dict[str, Any]
    caller: Caller


class Continue(Message):
    type: Literal["continue"] = "continue"
    run_id: uuid.UUID
    answer: Any


class Cancel(Message):
    type: Literal["cancel"] = "cancel"
    run_id: uuid.UUID


class Deploy(Message):
    """deploy, activate or remove one version; the token reads that one repo for an hour (none without a repo)."""

    type: Literal["deploy", "activate", "remove"]
    program: Name
    version: int
    repo: str | None
    commit_sha: Sha
    token: str | None


class SecretSet(Message):
    type: Literal["secret_set"] = "secret_set"
    program: Name
    name: Name
    value: str  # encrypted to the rrotor's public key, base64


Outbound = Welcome | Call | Continue | Cancel | Deploy | SecretSet | Ping | Pong | Ack
