"""Work that runs as a job (202, then GET /v1/jobs/{id} until done or failed): learn (the weights, then the
temperature) and calibrate (the temperature alone)."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from glyphh_ada.api.auth import AdaWho
from glyphh_ada.api.body import bounded
from glyphh_ada.api.call import call

router = APIRouter(tags=["jobs"], dependencies=[Depends(bounded)])


async def start(request: Request, who: AdaWho, name: str, kind: str) -> dict[str, Any]:
    return dict(await call(request, who, name, "job_start", {"kind": kind}))


@router.post("/v1/models/{name}/learn", operation_id="learnAdaModel", status_code=202)
async def learn(name: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """Learn each role's, value's, word's and pair's weight from the model's graded precedents, then calibrate."""
    return await start(request, who, name, "learn")


@router.post("/v1/models/{name}/calibrate", operation_id="calibrateAdaModel", status_code=202)
async def calibrate(name: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """Fit the temperature, so the probabilities mean what they say (or decide best, by the spec's costs)."""
    return await start(request, who, name, "calibrate")


@router.get("/v1/jobs/{job_id}", operation_id="getAdaJob")
async def get_job(job_id: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """A job's state (queued, running, done, failed), percent, and result or error."""
    return dict(await call(request, who, "", "job", {"id": job_id}))
