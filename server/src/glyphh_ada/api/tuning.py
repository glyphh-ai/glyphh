"""Tuning a model (docs/specs/ada-cloud.md, section 5): every change of its spec or settings is a new version, kept
with who made it and why; one is active, and any other can be made active again (a rollback). A backtest scores up
to ten candidates on the model's own held-out precedents first, without touching the live version.

A change answers {version, active, job}: active at once when the new version reads the stored cases as they are;
else `job` re-encodes them into a store of the new version's own while the old one serves, and makes it active when
done (GET /v1/jobs/{id})."""

from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from glyphh_ada import limits
from glyphh_ada.api.auth import AdaWho
from glyphh_ada.api.body import bounded
from glyphh_ada.api.call import call
from glyphh_ada.api.jobs import start

router = APIRouter(prefix="/v1/models/{name}", tags=["tuning"], dependencies=[Depends(bounded)])
NOTE = Field(None, max_length=500, description="Why: kept with the version")
BACKTEST = Field(None, description="The backtest job this change was chosen by: kept with the version")


class NewSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spec: dict[str, Any]
    note: str | None = NOTE
    backtest: str | None = BACKTEST


class Changes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: dict[str, Any] = Field(description="Settings to change: {lever: value}, each checked by the kernel")
    note: str | None = NOTE
    backtest: str | None = BACKTEST


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    settings: dict[str, Any] | None = Field(None, description="The active version's settings with these changed")
    spec_version: int | None = Field(None, ge=1, description="Another version of the model")
    spec: dict[str, Any] | None = Field(None, description="A whole spec")
    name: str | None = Field(None, max_length=80, description="What to call it in the answer")

    @model_validator(mode="after")
    def _one(self) -> "Candidate":
        if sum(x is not None for x in (self.settings, self.spec_version, self.spec)) != 1:
            raise ValueError("a candidate is one of settings, spec_version or spec")
        return self


class Holdout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    newest: int | None = Field(None, ge=1, le=limits.JOB_SAMPLE, description="The newest so many graded precedents")
    fraction: float | None = Field(None, gt=0, lt=1, description="Or a fraction of them, chosen by seed")
    seed: int = 0


class NewBacktest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates: list[Candidate] = Field(max_length=limits.CANDIDATES_MAX)
    holdout: Holdout = Field(default_factory=lambda: Holdout(newest=200))
    output: str | None = Field(None, description="A named output; left out, the default one")
    clearance: float = Field(1.0, ge=0, le=1)


def _changed(body: BaseModel) -> dict[str, Any]:
    return body.model_dump(exclude_none=True)


@router.put("/spec", operation_id="putAdaSpec")
async def put_spec(name: str, body: NewSpec, who: AdaWho, request: Request) -> dict[str, Any]:
    """A new version from a whole spec: {version, active, job}."""
    return dict(await call(request, who, name, "spec", _changed(body)))


@router.get("/settings", operation_id="getAdaSettings")
async def get_settings(name: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """Every lever as it stands on the active version: {version, settings}."""
    return dict(await call(request, who, name, "versions", {"levers": True}))


@router.patch("/settings", operation_id="patchAdaSettings")
async def patch_settings(name: str, body: Changes, who: AdaWho, request: Request) -> dict[str, Any]:
    """A new version with these settings changed: {version, active, job}."""
    return dict(await call(request, who, name, "settings", _changed(body)))


@router.get("/versions", operation_id="listAdaVersions")
async def list_versions(name: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """Every version: who made it and why, which is active, which were re-encoded, which can no longer be."""
    return {"versions": await call(request, who, name, "versions", {})}


@router.post("/versions/{version}/activate", operation_id="activateAdaVersion")
async def activate(name: str, version: int, who: AdaWho, request: Request) -> dict[str, Any]:
    """Make another version active (a rollback): at once, or by a job that brings its store up to date first."""
    return dict(await call(request, who, name, "activate", {"version": version}))


@router.post("/backtest", operation_id="backtestAdaModel", status_code=202)
async def backtest(name: str, body: NewBacktest, who: AdaWho, request: Request) -> dict[str, Any]:
    """Score the active version and up to ten candidates on the model's own held-out precedents, as a job."""
    args = body.model_dump(exclude_none=True)
    args["candidates"] = [c.model_dump(exclude_none=True) for c in body.candidates]
    return await start(request, who, name, "backtest", args)
