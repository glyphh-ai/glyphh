"""What the bot maker (ops/bots/maker.py) and the mascot drawer (ops/bots/mascot.py) take and answer."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.ops.bots.views import ScopeIn


class Said(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant"] = Field(description="user: the person; assistant: the bot maker")
    content: str = Field(min_length=1, max_length=8000)


class AppNeed(BaseModel):
    app: str = Field(description="A Pipedream app slug, e.g. gmail")
    tools: list[str] = Field(default_factory=list, description="Its tools the bot uses, by key")


class BotDraft(BaseModel):
    name: str
    summary: str = ""
    look: dict[str, str] = Field(default_factory=dict, description="Its cat: head, tail, eye, extra, accessory, pose")
    mascot: str = Field("", description="Its own drawn mascot (SVG), in place of the cat; empty for the cat")
    instructions: str
    model: str
    spec: dict[str, Any]
    skills: dict[str, str] = Field(default_factory=dict)
    apps: list[AppNeed] = Field(default_factory=list, description="The services it needs a connection to")
    connections: list[ScopeIn] = Field(
        default_factory=list, description="Its apps' tools scoped to the org's connections: POST /v1/bots takes them"
    )


class DraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    messages: list[Said] = Field(min_length=1, max_length=60, description="The conversation so far, oldest first")
    draft: dict[str, Any] | None = Field(None, description="The draft so far, to change rather than start again")


class DraftView(BaseModel):
    reply: str = Field(description="What the bot maker says next: a short question, or what it drafted")
    draft: BotDraft | None = Field(description="The bot as drafted so far, once there is enough to draft it")
    problems: list[str] = Field(description="What the SDK's check still finds wrong with the draft")
    missing_apps: list[str] = Field(description="The apps it needs that the org has not connected yet")


class MascotIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=1000, description="The mascot, described")


class MascotView(BaseModel):
    mascot: str = Field(description="The mascot: black-and-white SVG shapes, made safe")
