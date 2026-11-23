"""What the decisions routes and tools take and answer (docs/specs/bots.md, 12). A decision's name is its `gate`
field: a storage name kept from the first engine, nothing more."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Who = Literal["ada", "you", "default"]
Sort = Literal["time", "confidence", "gate", "outcome"]
WHO_ABOUT: str = "Who decided: ada (the decision's Ada model, sure enough), you (the person was asked) or default"
NAME: str = "The decision's name"


class DecisionView(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID | None = Field(description="The bot run it was made in; none for a case added by hand")
    gate: str = Field(description=NAME)
    step: str
    key: str = Field(description="The item's key in its run")
    kind: str = Field(description="gate (one case a run), each (one item of many), code, or case (added by hand)")
    label: str = Field(description="The item's title or summary, drawn from its fields")
    fields: dict[str, str] = Field(description="The item's fields, readable: name to text")
    outcome: str | None = Field(description="What was decided")
    now: str | None = Field(description="What it is now: the corrected outcome when it was corrected, else outcome")
    who: Who = Field(description=WHO_ABOUT)
    mode: str = Field(description="Why the person was asked: new, few, unsure, audit or shadow; empty when not")
    confidence: float | None = Field(description="Ada's probability for its call (for a person's, Ada's guess's)")
    guess: str | None = Field(description="Ada's guess, when the person decided")
    recorded: bool = Field(description="It is a precedent of the decision's Ada model")
    corrected: str | None = Field(description="What it should have been, when it was corrected")
    confirmed: bool = Field(description="The person said it was right")
    outcomes: list[str] = Field(description="The decision's outcomes")
    at: datetime


class DecisionPage(BaseModel):
    decisions: list[DecisionView]
    total: int = Field(description="How many match the search and filters")
    next_cursor: str | None = Field(description="The next page's cursor; none on the last page")
    gates: dict[str, list[str]] = Field(description="The bot's decisions, each with its outcomes")


class Precedent(BaseModel):
    id: str = Field(description="The precedent's id in the decision's Ada model (bot_forget_case forgets it)")
    outcome: Any
    similarity: float | None = Field(description="How alike it is to this decision's case, 0 to 1")
    label: str | None = Field(None, description="Its item's label, when it is one of the bot's decisions")
    decision_id: uuid.UUID | None = None


class DecisionDetail(DecisionView):
    case: Any = Field(description="What the decision's Ada model read")
    precedents: list[Precedent] = Field(description="The nearest precedents Ada stands on now, nearest first")


class RelabelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outcome: str = Field(min_length=1, max_length=200, description="What it should have been: one of its outcomes")


class IdsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ids: list[uuid.UUID] = Field(min_length=1, max_length=200, description="Decisions of one kind, by id")


class RelabelManyIn(IdsIn, RelabelIn):
    pass


class CaseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gate: str = Field(min_length=1, max_length=100, description=NAME)
    outcome: str = Field(min_length=1, max_length=200, description="Its outcome: one of the decision's")
    item: dict[str, Any] | None = Field(
        None, description="The item, its fields as a run gives them (the case is made from it as a run does)"
    )
    case: dict[str, Any] | None = Field(None, description="Else the case itself, in the decision's spec's shape")
    label: str = Field("", max_length=200, description="A title for it; else one is drawn from its fields")


class Trained(BaseModel):
    decisions: list[DecisionView] = Field(description="The decisions as they are now")
    precedents: int = Field(description="How many precedents the decision's Ada model holds now")
    said: str = Field(description="What was done, in a line")


class Forgot(BaseModel):
    gate: str
    id: str
    precedents: int


class GateDay(BaseModel):
    day: str
    decisions: int
    ask_rate: float | None
    agreement: float | None
    accuracy: float | None


class GateStats(BaseModel):
    gate: str = Field(description=NAME)
    decisions: int
    by: dict[str, int] = Field(description="How many Ada, you and the default decided")
    corrected: int
    confirmed: int
    ask_rate: float | None = Field(description="Of its decisions, the share the person was asked")
    agreement: float | None = Field(description="Of the person's answers where Ada had a guess, the share it agreed")
    accuracy: float | None = Field(description="Of Ada's own calls the person checked, the share that were right")
    days: list[GateDay] = Field(description="The same, day by day, oldest first")


class Stats(BaseModel):
    gates: list[GateStats]


class BacktestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gate: str | None = Field(None, max_length=100, description="One decision; else every one")
    limit: int = Field(50, ge=1, le=200, description="How many of the newest decisions to replay")


class Change(BaseModel):
    decision: DecisionView
    then: str | None = Field(description="What it is (corrected, else what was said)")
    now: str | None = Field(description="What Ada would say now")
    ask: bool = Field(description="Whether Ada would be unsure now")
    confidence: float | None


class Backtest(BaseModel):
    replayed: int
    same: int
    changed: list[Change]
    would_ask: int = Field(description="How many Ada would be unsure of now")
    right_now: int = Field(description="How many it would now get right (its call is what the decision is)")
