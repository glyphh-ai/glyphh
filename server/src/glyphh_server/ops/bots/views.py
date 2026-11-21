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


SPEC_ABOUT: str = (
    "The bot's loop, as the SDK's bot.json has it but its slug, name and agent (bot_guide says how): loop (its "
    "steps: run a tool, a gate that learns in Ada, an agent step Claude does, a ladder), gates, touches, hosts, "
    "limits, seed"
)
SKILLS_ABOUT: str = "Its skills, by name: each a SKILL.md, how its agent does one kind of step"
INSTRUCTIONS_ABOUT: str = "Its agent's prompt: who it is and how it works (agent.md's body)"


class Scope(BaseModel):
    connection_id: uuid.UUID
    app: str
    app_name: str
    tools: list[str] = Field(description="The connection's tools the bot may use, by key")


class ScopeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: uuid.UUID
    tools: list[str] = Field(max_length=200, description="The connection's tools the bot may use, by key")


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
    instructions: str = Field(description=INSTRUCTIONS_ABOUT)
    model: str = Field(description="The Claude model its agent steps run on")
    spec: dict[str, Any] = Field(description=SPEC_ABOUT)
    skills: dict[str, str] = Field(description=SKILLS_ABOUT)
    gate_models: list[str] = Field(description="Its own Ada models: one per gate, and its memory")
    connections: list[Scope]
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
    instructions: str = Field(min_length=1, max_length=20_000, description=INSTRUCTIONS_ABOUT)
    model: str | None = Field(None, description="A Claude model bot_models lists; left out, the default")
    spec: dict[str, Any] = Field(description=SPEC_ABOUT)
    skills: dict[str, str] = Field(default_factory=dict, max_length=30, description=SKILLS_ABOUT)
    connections: list[ScopeIn] = Field(
        default_factory=list, max_length=50, description="Per connection, the tools it may use (its steps name them)"
    )


class BotPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=80, description="Its name; its slug stays")
    summary: str | None = Field(None, max_length=500)
    look: dict[str, str] | None = None
    instructions: str | None = Field(None, min_length=1, max_length=20_000, description=INSTRUCTIONS_ABOUT)
    model: str | None = None
    spec: dict[str, Any] | None = Field(None, description=SPEC_ABOUT)
    skills: dict[str, str] | None = Field(None, max_length=30, description=SKILLS_ABOUT)


class ScopesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connections: list[ScopeIn] = Field(max_length=50)


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str = Field("", max_length=200_000, description="What the bot is given to work on: $input to its steps")


class Question(BaseModel):
    question: str = Field(description="What the run asks the person")
    options: list[str] = Field(description="The answers it takes")
    batch: list[dict[str, Any]] | None = Field(None, description="For a gate over many items: each item, numbered")
    answer_with: str | None = Field(None, description="How a batch is answered: N=option for each, rest=option")


class RunView(BaseModel):
    id: uuid.UUID
    bot_slug: str
    status: str = Field(description="queued, running, needs_input (it waits on the person), done, failed or skipped")
    input: str
    output: str = Field(description="Its last step's answer, as text")
    error: str = Field(description="Why it failed, ended early or was skipped")
    log: list[str] = Field(description="What it did, line by line")
    data: dict[str, Any] = Field(description="Each step's answer, by step id")
    question: Question | None = Field(description="What it waits on, when it needs input")
    input_tokens: int
    output_tokens: int
    cost_micros: int = Field(description="What its tokens were charged, microdollars: 0 on the org's own key")
    own_key: bool = Field(description="Its agent steps ran on the org's own Anthropic key")
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class Runs(BaseModel):
    runs: list[RunView]


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str | list[str] | dict[str, str] = Field(
        description="One of the question's options; for a batch, N=option for each (rest=option), or a map"
    )


class WrongIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str = Field(min_length=1, max_length=200, description="What the gate should have said")
    gate: str | None = Field(None, max_length=100, description="Which gate, when the run had more than one")
    item: str | None = Field(None, max_length=200, description="Which item, for a gate over many: its key")


class KeyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=20, max_length=500, description="The org's Anthropic API key (sk-ant-...)")


class KeyView(BaseModel):
    set: bool = Field(description="The org's bots run on its own Anthropic key")
    hint: str = Field(description="Its last four characters")
    set_at: datetime | None
    glyphh_key: bool = Field(description="Without one, they run on Glyphh's, billed by tokens")


class Gates(BaseModel):
    gates: dict[str, Any] = Field(description="Each gate: its model, precedents, how often it asked and was right")
