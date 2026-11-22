"""What the bots and connections routes and tools take and answer (docs/specs/bots.md)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.ops.bots.access import Chosen, ChosenIn, ChosenPatch
from glyphh_server.ops.bots.exposed import ABOUT as TOOLS_ABOUT
from glyphh_server.ops.bots.exposed import ConnectorTool
from glyphh_server.ops.bots.schedule import Schedule
from glyphh_server.ops.bots.shown import Shown

LOOK_PARTS: tuple[str, ...] = ("head", "tail", "eye", "extra", "accessory", "pose")


SPEC_ABOUT: str = (
    "The bot's loop, as the SDK's bot.json has it but its slug, name and agent (bot_guide says how): loop (its "
    "steps: run a tool, a gate that learns in Ada, an agent step Claude does, a ladder), gates, touches, hosts, "
    "limits, seed"
)
SKILLS_ABOUT: str = "Its skills, by name: each a SKILL.md, how its agent does one kind of step"
INSTRUCTIONS_ABOUT: str = "Its agent's prompt: who it is and how it works (agent.md's body)"
MASCOT_ABOUT: str = "Its own drawn mascot (black-and-white SVG, made safe), shown in place of its cat; empty: the cat"
MASCOT_MAX: int = 30_000
Mode = Literal["ask", "connection", "auto"]
MODE_ABOUT: str = (
    "Which tool steps wait for the person's yes: ask (each, unless its connection allows the tool), connection (only "
    "those its connection says to ask about) or auto (none); a tool its connection denies always fails"
)
VOICE_ABOUT: str = "The voice it speaks in, one GET /v1/bots/voices lists; empty for none"
SCHEDULE_ABOUT: str = "When it runs on its own, in plain words (every: off, hour, day, weekdays, week, month)"
RUNS_ON_ABOUT: str = "Where it runs: a rrotor of the org's (GET /v1/bots/places lists them), or none for Glyphh cloud"


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


class BotView(Chosen):  # with its folders and effort (ops/bots/access.py)
    id: uuid.UUID
    slug: str
    name: str
    summary: str
    look: dict[str, str] = Field(description="Its cat: head, tail, eye, extra, accessory, pose")
    mascot: str = Field(description=MASCOT_ABOUT)
    instructions: str = Field(description=INSTRUCTIONS_ABOUT)
    model: str = Field(description="The Claude model its agent steps run on")
    permission_mode: Mode = Field(description=MODE_ABOUT)
    voice: str = Field(description=VOICE_ABOUT)
    spec: dict[str, Any] = Field(description=SPEC_ABOUT)
    skills: dict[str, str] = Field(description=SKILLS_ABOUT)
    gate_models: list[str] = Field(description="Its own Ada models: one per gate, and its memory")
    connections: list[Scope]
    schedule: Schedule = Field(description=SCHEDULE_ABOUT)
    schedule_summary: str = Field(description="Its schedule in plain words: Every day at 9:00")
    next_run_at: datetime | None = Field(description="When the schedule runs it next")
    next_run: str = Field(description="When, in the schedule's time zone: Mon 9:00; empty when it is off")
    runs_on: uuid.UUID | None = Field(description=RUNS_ON_ABOUT)
    connector_tools: list[ConnectorTool] = Field(description=TOOLS_ABOUT)
    created_at: datetime
    updated_at: datetime
    last_run: LastRun | None


class Bots(BaseModel):
    bots: list[BotView]


class BotIn(ChosenIn):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    summary: str = Field("", max_length=500)
    look: dict[str, str] = Field(default_factory=dict, description="Its cat: head, tail, eye, extra, accessory, pose")
    mascot: str = Field("", max_length=MASCOT_MAX, description=MASCOT_ABOUT)
    instructions: str = Field(min_length=1, max_length=20_000, description=INSTRUCTIONS_ABOUT)
    model: str | None = Field(None, description="A Claude model bot_models lists; left out, the default")
    permission_mode: Mode = Field("ask", description=MODE_ABOUT)
    voice: str = Field("", max_length=40, description=VOICE_ABOUT)
    spec: dict[str, Any] = Field(description=SPEC_ABOUT)
    skills: dict[str, str] = Field(default_factory=dict, max_length=30, description=SKILLS_ABOUT)
    connections: list[ScopeIn] = Field(
        default_factory=list, max_length=50, description="Per connection, the tools it may use (its steps name them)"
    )
    schedule: Schedule = Field(default_factory=Schedule, description=SCHEDULE_ABOUT)
    runs_on: uuid.UUID | None = Field(None, description=RUNS_ON_ABOUT)
    connector_tools: list[ConnectorTool] = Field(default_factory=list, max_length=20, description=TOOLS_ABOUT)


class BotPatch(ChosenPatch):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=80, description="Its name; its slug stays")
    summary: str | None = Field(None, max_length=500)
    look: dict[str, str] | None = None
    mascot: str | None = Field(None, max_length=MASCOT_MAX, description=MASCOT_ABOUT)
    instructions: str | None = Field(None, min_length=1, max_length=20_000, description=INSTRUCTIONS_ABOUT)
    model: str | None = None
    permission_mode: Mode | None = Field(None, description=MODE_ABOUT)
    voice: str | None = Field(None, max_length=40, description=VOICE_ABOUT)
    spec: dict[str, Any] | None = Field(None, description=SPEC_ABOUT)
    skills: dict[str, str] | None = Field(None, max_length=30, description=SKILLS_ABOUT)
    schedule: Schedule | None = Field(None, description=SCHEDULE_ABOUT)
    runs_on: uuid.UUID | None = Field(None, description=RUNS_ON_ABOUT + " (null: back to Glyphh cloud)")
    connector_tools: list[ConnectorTool] | None = Field(None, max_length=20, description=TOOLS_ABOUT)


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
    step: str | None = Field(None, description="The step of its loop it waits at")
    approval: bool = Field(False, description="An approval: the person's yes (or no) before the step acts")


class RunView(Shown):
    id: uuid.UUID
    bot_slug: str
    status: str = Field(
        description="queued, running, dispatched (sent to its rrotor), needs_input (it waits on the person), done, "
        "failed or skipped"
    )
    input: str
    output: str = Field(description="Its last step's answer, as text")
    error: str = Field(description="Why it failed, ended early or was skipped")
    log: list[str] = Field(description="What it did, line by line")
    data: dict[str, Any] = Field(description="Each step's answer, by step id")
    question: Question | None = Field(description="What it waits on, when it needs input")
    input_tokens: int
    output_tokens: int
    cost_micros: int = Field(description="Its tokens' charge, microdollars (the markup alone on the org's own key)")
    own_key: bool = Field(description="Its agent steps ran on the org's own Anthropic key")
    runs_on: uuid.UUID | None = Field(None, description="The org's rrotor it ran on; none for Glyphh cloud")
    kind: Literal["bot", "project"] = Field("bot", description="In the approvals queue: a bot's run, or a project's")
    project_slug: str | None = Field(
        None, description="A project's run: its project (POST /v1/project-runs/{id}/answer)"
    )
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
