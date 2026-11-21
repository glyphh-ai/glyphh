"""What the bots and connections routes and tools take and answer (docs/specs/bots.md)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

LOOK_PARTS: tuple[str, ...] = ("head", "tail", "eye", "extra", "accessory", "pose")


class ConnectionView(BaseModel):
    id: uuid.UUID
    app: str = Field(description="The service, as Pipedream names it (gmail, slack, ...)")
    app_name: str
    app_icon: str
    account_id: str
    label: str = Field(description="The account's own name at the service")
    created_at: datetime


class Connections(BaseModel):
    connections: list[ConnectionView]


class AppView(BaseModel):
    slug: str
    name: str
    description: str
    icon: str


class Apps(BaseModel):
    apps: list[AppView]
    next_cursor: str | None


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app: str = Field(min_length=1, max_length=200, description="The service's slug (connection_apps lists them)")


class Link(BaseModel):
    url: str = Field(description="Pipedream's page where the person signs in to the service for the org")
    expires_at: str | None


class ToolView(BaseModel):
    key: str = Field(description="The tool's key, as a bot's scope names it")
    name: str
    description: str


class Tools(BaseModel):
    tools: list[ToolView]


class Limits(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_turns: int = Field(20, ge=1, le=200, description="Claude's turns a run may take")
    usd_per_run: float = Field(2.0, gt=0, le=100, description="What a run may spend on tokens, US dollars")


class Scope(BaseModel):
    connection_id: uuid.UUID
    app: str
    app_name: str
    tools: list[str] = Field(description="The connection's tools the bot may use, by key")


class LastRun(BaseModel):
    id: uuid.UUID
    status: str
    created_at: datetime


class BotView(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    summary: str
    look: dict[str, str] = Field(description="Its cat: head, tail, eye, extra, accessory, pose")
    instructions: str
    model: str
    models: list[str] = Field(description="The Ada models it may ask and teach")
    connections: list[Scope]
    limits: Limits
    created_at: datetime
    updated_at: datetime
    last_run: LastRun | None


class Bots(BaseModel):
    bots: list[BotView]


class BotIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    summary: str = Field("", max_length=500)
    look: dict[str, str] = Field(default_factory=dict, description="Its cat: head, tail, eye, extra, accessory, pose")
    instructions: str = Field("", max_length=20_000, description="What it does, how, and when to stop")
    model: str | None = Field(None, description="A Claude model bot_models lists; left out, the default")
    models: list[str] = Field(default_factory=list, max_length=20, description="Ada models it may ask and teach")
    limits: Limits | None = None


class BotPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=80)
    summary: str | None = Field(None, max_length=500)
    look: dict[str, str] | None = None
    instructions: str | None = Field(None, max_length=20_000)
    model: str | None = None
    models: list[str] | None = Field(None, max_length=20)
    limits: Limits | None = None


class ScopeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: uuid.UUID
    tools: list[str] = Field(max_length=200)


class ScopesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connections: list[ScopeIn] = Field(max_length=50)


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str = Field("", max_length=200_000, description="What the bot is given to work on")


class Step(BaseModel):
    kind: str = Field(description="text (what Claude said), tool (a connection's tool) or ada (an Ada model)")
    name: str
    input: Any = None
    output: Any = None
    is_error: bool = False
    at: datetime


class RunView(BaseModel):
    id: uuid.UUID
    bot_slug: str
    status: str = Field(description="queued, running, done or failed")
    input: str
    output: str
    error: str
    steps: list[Step]
    input_tokens: int
    output_tokens: int
    cost_micros: int = Field(description="What its tokens were charged, microdollars (past the plan's allowance)")
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class Runs(BaseModel):
    runs: list[RunView]
