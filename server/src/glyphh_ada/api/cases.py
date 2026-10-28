"""Writing a model's cases: record one, record many in one transaction, grade one already recorded, forget one. Every
write takes an Idempotency-Key: the same key and body answer the first answer, and write nothing again."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from glyphh_ada import limits
from glyphh_ada.api.auth import AdaWho
from glyphh_ada.api.body import bounded
from glyphh_ada.api.call import call

router = APIRouter(prefix="/v1/models/{name}", tags=["cases"], dependencies=[Depends(bounded)])

# a named output's outcome by its kind: a choice's or score's value, a noul's true/false, a number, a many's list
Outcome = str | bool | float | list[str]
OUTCOME = "By the output's kind: one of its values, true/false (noul), a number (number), a list of values (many)"


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: dict[str, Any] = Field(description="The case in the spec's shape: layers, segments, roles")
    outcome: str | None = Field(None, min_length=1, description="The default output's outcome, when known")
    outcomes: dict[str, Outcome] | None = Field(
        None, description=f"Named outputs' outcomes: {{output: value}}. {OUTCOME}"
    )
    ts: float | None = Field(None, description="When it happened, epoch seconds; else the spec's or now")


class Cases(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cases: list[dict[str, Any]] = Field(max_length=limits.RECORD_MANY_MAX, description="Each {data, outcome?, ...}")


class Grade(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=200)
    output: str | None = Field(None, description="A named output; left out, the default one")
    value: Outcome | None = Field(None, description=f"The outcome; null takes it away. {OUTCOME}")


@router.post("/record", operation_id="recordAdaCase")
async def record(name: str, body: Case, who: AdaWho, request: Request) -> dict[str, Any]:
    """One case: its id (the spec's key parts make it, or a new one) and how many precedents the model holds."""
    return dict(await call(request, who, name, "record", body.model_dump(exclude_none=True)))


@router.post("/record_many", operation_id="recordManyAdaCases")
async def record_many(name: str, body: Cases, who: AdaWho, request: Request) -> dict[str, Any]:
    """Up to 1,000 cases in one transaction, all or none: {ids, added, replaced, precedents}."""
    return dict(await call(request, who, name, "record_many", body.model_dump()))


@router.post("/grade", operation_id="gradeAdaCase")
async def grade(name: str, body: Grade, who: AdaWho, request: Request) -> dict[str, Any]:
    """One output's outcome on a case already recorded."""
    return dict(await call(request, who, name, "grade", body.model_dump()))


@router.delete("/precedents/{precedent_id}", operation_id="forgetAdaCase")
async def forget(name: str, precedent_id: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """Forget one case and every outcome it carries; what was learned from it stays until the next learn."""
    return dict(await call(request, who, name, "forget", {"id": precedent_id}))
