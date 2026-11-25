"""The Glyphh-hosted models (docs/specs/tokens.md), from models.json, as ada_versions.json lists Ada's versions: each
an id customers send as `model` (`adal-34b-1-0`), its rates in cents per million input and output tokens, and how much
of a plan's monthly allowance a token uses. Checked when read: a bad list stops the server's start."""

import json
import math
import re
from dataclasses import dataclass
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

FILE: Path = Path(__file__).with_name("models.json")
ID: re.Pattern[str] = re.compile(r"^adal-\d+[a-z]-\d+-\d+(-beta)?$")
STATUSES: tuple[str, ...] = ("beta", "stable", "deprecated")


@dataclass(frozen=True)
class Model:
    id: str
    name: str
    status: str
    context_tokens: int
    input_cents_per_mtok: int
    output_cents_per_mtok: int
    allowance_weight: float
    released: date
    summary: str

    def weighed(self, input_tokens: int, output_tokens: int) -> int:
        """The allowance a request's tokens use: (input + output) x weight, rounded up."""
        return math.ceil((input_tokens + output_tokens) * self.allowance_weight)

    def cost_micros(self, input_tokens: int, output_tokens: int, share: float = 1.0) -> int:
        """What the tokens cost in microdollars, rounded up: a cent per million tokens is 0.01 micros a token.
        `share`: the part of the request past the allowance."""
        cents = input_tokens * self.input_cents_per_mtok + output_tokens * self.output_cents_per_mtok
        return math.ceil(cents * share / 100) if share > 0 else 0


class ModelView(BaseModel):
    id: str = Field(description="What a request sends as `model`")
    name: str
    status: str = Field(description="beta, stable or deprecated (still answers; move off it)")
    context_tokens: int = Field(description="Input and output tokens a request may hold together")
    input_cents_per_mtok: int = Field(description="US cents per million input tokens past the allowance")
    output_cents_per_mtok: int = Field(description="US cents per million output tokens past the allowance")
    allowance_weight: float = Field(description="Allowance a token uses: (input + output) x weight")
    released: date
    summary: str


class Models(BaseModel):
    models: list[ModelView]


def _model(raw: dict[str, Any]) -> Model:
    found = Model(**{**raw, "released": date.fromisoformat(raw["released"])})
    if not ID.fullmatch(found.id) or found.status not in STATUSES:
        raise RuntimeError(f"models.json: {found.id!r} is not an adal-<size>-<major>-<minor> id of a known status")
    if min(found.input_cents_per_mtok, found.output_cents_per_mtok, found.context_tokens) < 0:
        raise RuntimeError(f"models.json: {found.id}'s rates and context are never negative")
    if found.allowance_weight <= 0:
        raise RuntimeError(f"models.json: {found.id}'s allowance_weight is above 0")
    return found


def parse(raw: dict[str, Any]) -> dict[str, Model]:
    models = [_model(m) for m in raw["models"]]
    if len({m.id for m in models}) != len(models):
        raise RuntimeError("models.json: an id is listed twice")
    return {m.id: m for m in models}


@cache
def models() -> dict[str, Model]:
    return parse(json.loads(FILE.read_text()))


def find(model_id: object) -> Model | None:
    return models().get(model_id) if isinstance(model_id, str) else None


def view(m: Model) -> ModelView:
    return ModelView(**m.__dict__)


def listing() -> Models:
    return Models(models=[view(m) for m in models().values()])
