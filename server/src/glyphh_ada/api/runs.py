"""`POST /v1/runs`, the SDK 3.0 runs shape (glyphh contract/contract.json, `result`), so SDK 3.0 works against the cloud
with only its URL (GLYPHH_RUNTIME_URL=https://ada.glyphh.ai) and key changed. A run of record, query, facts,
probabilities, decide, learn or settings is answered at once as a `done` Result: a fresh run_id, `seconds` the time
it took. learn waits for its job up to LEARN_WAIT seconds, then answers the job as it stands. The cloud keeps no runs,
so there is nothing to continue: a decide that should ask a person answers `ask: true`, never `needs_input`."""

import asyncio
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from glyphh_ada.api.auth import AdaCaller, AdaWho
from glyphh_ada.api.body import bounded
from glyphh_ada.api.call import call, versioned
from glyphh_ada.errors import Refused

router = APIRouter(prefix="/v1/runs", tags=["runs"])

LEARN_WAIT: float = 60.0
POLL: float = 0.5
INPUTS: dict[str, tuple[str, ...]] = {
    "record": ("data", "outcome", "outcomes", "ts"),
    "query": ("data", "output"),
    "probabilities": ("data", "output"),
    "facts": ("data", "top", "min_score", "output"),
    "decide": ("data", "output", "outputs", "include"),
}


class Run(BaseModel):
    model: str = Field(min_length=1, max_length=63)
    function: str = Field(min_length=1, max_length=63)
    inputs: dict[str, Any] = Field(default_factory=dict)
    clearance: float | None = Field(None, ge=0, le=1)
    version: int | None = Field(None, description="Ignored: the cloud answers from the active version")


async def _learn(request: Request, who: AdaCaller, model: str) -> tuple[Any, int | None]:
    job, version = await versioned(request, who, model, "job_start", {"kind": "learn"})
    deadline = time.monotonic() + LEARN_WAIT
    while job["state"] not in ("done", "failed") and time.monotonic() < deadline:
        await asyncio.sleep(POLL)
        job = await call(request, who, "", "job", {"id": job["id"]})
    if job["state"] == "failed":
        error = dict(job["error"] or {})
        raise Refused(error.pop("code", "E_INTERNAL"), error.pop("message", "learn failed"), 422, **error)
    return (job["result"] if job["state"] == "done" else {"job": job}), version


async def _answer(request: Request, who: AdaCaller, body: Run) -> tuple[Any, int | None]:
    if body.function == "learn":
        return await _learn(request, who, body.model)
    if body.function == "settings":
        found, version = await versioned(request, who, body.model, "model", {})
        return found["spec"].get("settings", {}), version
    if body.function not in INPUTS:
        await call(request, who, body.model, "model", {})  # a model that is not there says so first, as the SDK expects
        raise Refused("E_FUNCTION_MISSING", f"An Ada Cloud model has no function {body.function}.", 404)
    args = {k: body.inputs[k] for k in INPUTS[body.function] if body.inputs.get(k) is not None}
    return await versioned(request, who, body.model, body.function, args, body.clearance)


@router.post("", operation_id="run", dependencies=[Depends(bounded)])
async def run(body: Run, who: AdaWho, request: Request) -> dict[str, Any]:
    """One function of a model, answered as the SDK 3.0 runs shape's Result: {run_id, model, version, function,
    status: done, data, step, prompt, seconds}."""
    started = time.perf_counter()
    data, version = await _answer(request, who, body)
    return {
        "run_id": uuid.uuid4().hex[:12],
        "model": body.model,
        "version": version or 1,
        "function": body.function,
        "status": "done",
        "data": data,
        "step": None,
        "prompt": None,
        "seconds": round(time.perf_counter() - started, 4),
    }


def _no_run(run_id: str) -> Refused:
    return Refused("E_RUN_MISSING", f"No run {run_id}: Ada Cloud answers every run at once and keeps none.", 404)


@router.get("/{run_id}", operation_id="getRun")
async def get_run(run_id: str, who: AdaWho) -> None:
    """The cloud keeps no runs: every run is answered at once, so none can be read."""
    raise _no_run(run_id)


@router.api_route("/{run_id}/{action}", methods=["GET", "POST"], operation_id="continueRun")
async def continue_run(run_id: str, action: str, who: AdaWho) -> None:
    """Nor continued, cancelled or logged."""
    raise _no_run(run_id)
