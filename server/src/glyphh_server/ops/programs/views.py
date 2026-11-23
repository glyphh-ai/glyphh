"""What the programs' routes and connector tools take and answer (docs/specs/programs.md, 6)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from glyphh_server.ops.bots.schedule import Schedule

SOURCE_MAX: int = 200_000
RUNS_ON_ABOUT: str = "Where it runs: none for Glyphh cloud, or the id of one of the org's rrotors"


class ProgramIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    summary: str = Field("", max_length=300)
    source: str | None = Field(None, max_length=SOURCE_MAX, description="program.py's whole text")
    flow: list[dict[str, Any]] | None = Field(None, description="Its steps, written into program.py as FLOW")
    bot: str | None = Field(None, description="The bot (its slug) whose tools it uses and who does unnamed steps")
    runs_on: uuid.UUID | None = Field(None, description=RUNS_ON_ABOUT)
    schedule: Schedule = Field(default_factory=Schedule)


class ProgramPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=80)
    summary: str | None = Field(None, max_length=300)
    source: str | None = Field(None, max_length=SOURCE_MAX)
    flow: list[dict[str, Any]] | None = None
    bot: str | None = None
    runs_on: uuid.UUID | None = Field(None, description=RUNS_ON_ABOUT)
    schedule: Schedule | None = None


class ProgramView(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    summary: str
    bot: str | None = Field(description="Its own bot, by slug")
    source: str
    flow: list[dict[str, Any]]
    functions: list[str]
    problems: list[str]
    runs_on: uuid.UUID | None
    can_run_on: list[str]
    schedule: Schedule
    schedule_summary: str
    next_run_at: datetime | None
    next_run: str
    template: str
    last_run: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class Programs(BaseModel):
    programs: list[ProgramView]


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str = Field("", max_length=20_000)


class AnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: Any


class ProgramRunView(BaseModel):
    id: uuid.UUID
    program: str
    status: str
    trigger: str
    input: str
    at: str
    outputs: dict[str, Any]
    question: dict[str, Any] | None
    error: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ProgramRuns(BaseModel):
    runs: list[ProgramRunView]


class EventView(BaseModel):
    n: int
    at: datetime
    kind: str
    step: str
    title: str
    bot: str | None
    by: str | None
    ok: bool
    detail: str


class Events(BaseModel):
    events: list[EventView]


class FoundTool(BaseModel):
    key: str
    title: str
    app: str
    description: str
    read_only: bool
    connection_id: uuid.UUID | None
    added: bool


class FoundTools(BaseModel):
    tools: list[FoundTool]


class AddToolIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: uuid.UUID | None = Field(None, description="The connection the tool is of; none for a built-in")
    tool: str = Field(min_length=1, max_length=200)
