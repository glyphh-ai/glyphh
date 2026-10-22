"""Asking a model: query, probabilities, facts and decide, the kernel's own answers; and `POST /v1/decide`, the
headline: {outcome, probabilities, expected_cost, ask, receipts, model, version}. Clearance is the key's, or lower
when the request asks for less."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from glyphh_ada import limits
from glyphh_ada.api.auth import AdaWho
from glyphh_ada.api.body import bounded
from glyphh_ada.api.call import call, versioned

router = APIRouter(tags=["reads"], dependencies=[Depends(bounded)])


class Ask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: dict[str, Any] = Field(description="The case in the spec's shape; what it leaves out weighs nothing")
    output: str | None = Field(None, description="A named output; left out, the default one")
    clearance: float | None = Field(None, ge=0, le=1, description="Read with less clearance than the key's")


class FactsAsk(Ask):
    top: int | None = Field(None, ge=1, le=limits.FACTS_TOP_MAX)
    min_score: float | None = Field(None, ge=0, le=1)


class DecideAsk(Ask):
    outputs: list[str] | None = Field(None, max_length=limits.OUTPUTS_MAX, description="Decide these outputs at once")
    include: list[Literal["facts"]] | None = Field(None, description='["facts"]: the nearest fact tree too')


class Decide(DecideAsk):
    model: str = Field(min_length=1, max_length=63)


def _args(body: BaseModel) -> dict[str, Any]:
    return body.model_dump(exclude_none=True, exclude={"clearance", "model"})


@router.post("/v1/models/{name}/query", operation_id="queryAdaModel")
async def query(name: str, body: Ask, who: AdaWho, request: Request) -> dict[str, Any]:
    """The nearest precedents' vote: {sufficient, confidence, support, count, top, outcomes, receipts}."""
    return dict(await call(request, who, name, "query", _args(body), body.clearance))


@router.post("/v1/models/{name}/probabilities", operation_id="probabilitiesAdaModel")
async def probabilities(name: str, body: Ask, who: AdaWho, request: Request) -> dict[str, float]:
    """P(outcome | data), calibrated."""
    return dict(await call(request, who, name, "probabilities", _args(body), body.clearance))


@router.post("/v1/models/{name}/facts", operation_id="factsAdaModel")
async def facts(name: str, body: FactsAsk, who: AdaWho, request: Request) -> list[dict[str, Any]]:
    """The fact trees, best first, each cut to what the caller's clearance may see."""
    return list(await call(request, who, name, "facts", _args(body), body.clearance))


@router.post("/v1/models/{name}/decide", operation_id="decideAdaModel")
async def decide_model(name: str, body: DecideAsk, who: AdaWho, request: Request) -> dict[str, Any]:
    """The outcome of least expected cost, its probabilities, whether a person should decide, and the receipts."""
    return dict(await call(request, who, name, "decide", _args(body), body.clearance))


@router.post("/v1/decide", operation_id="decide")
async def decide(body: Decide, who: AdaWho, request: Request) -> dict[str, Any]:
    """The headline: one call, one typed answer: {outcome, probabilities, expected_cost, ask, receipts, model,
    version}."""
    answer, version = await versioned(request, who, body.model, "decide", _args(body), body.clearance)
    return {**answer, "model": body.model, "version": version}
