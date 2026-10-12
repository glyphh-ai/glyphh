"""The machine link's protocol, version 1, as the server reads it and writes it (rrotor's `engine/src/wire.ts`).
The machine says hello and reports every session's events, numbered within their thread; the server starts,
speaks to, answers and stops sessions, and deletes threads."""

import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

PROTOCOL: int = 1


class Hello(BaseModel):
    type: Literal["hello"]
    protocol: int
    version: str = Field(max_length=100)


class SessionEvent(BaseModel):
    type: Literal["session.event"]
    session: str = Field(max_length=200)
    thread: uuid.UUID
    super_power: uuid.UUID | None = None
    seq: int = Field(ge=1)
    at: str = Field(max_length=40)
    event: dict[str, Any]


class SessionRefused(BaseModel):
    type: Literal["session.refused"]
    session: str = Field(max_length=200)
    thread: uuid.UUID | None = None
    reason: str = Field(max_length=1000)


Report = Annotated[Hello | SessionEvent | SessionRefused, Field(discriminator="type")]
REPORT: TypeAdapter[Hello | SessionEvent | SessionRefused] = TypeAdapter(Report)


def start(
    thread: uuid.UUID, super_power: uuid.UUID | None, engine: str, prompt: str, model: str | None, mode: str
) -> dict[str, Any]:
    """A thread's lead session: its id is the thread's own."""
    msg = {
        "type": "session.start",
        "session": str(thread),
        "thread": str(thread),
        "engine": engine,
        "prompt": prompt,
        "mode": mode,
    }
    if super_power:
        msg["super_power"] = str(super_power)
    if model:
        msg["model"] = model
    return msg


def say(session: str, text: str) -> dict[str, Any]:
    return {"type": "session.send", "session": session, "text": text}


def answer(session: str, ask_id: str, allow: bool) -> dict[str, Any]:
    return {"type": "session.answer", "session": session, "id": ask_id, "allow": allow}


def stop(session: str) -> dict[str, Any]:
    return {"type": "session.stop", "session": session}


def forget(thread: uuid.UUID) -> dict[str, Any]:
    """Delete a thread's events on the machine, for good."""
    return {"type": "thread.delete", "thread": str(thread)}
