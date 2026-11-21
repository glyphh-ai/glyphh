"""Work that runs as a job (202, then GET /v1/jobs/{id} until done or failed): learn (the weights, then the
temperature), calibrate (the temperature alone) and export (everything of a model, by a download link that a done
export's job carries for limits.LINK_TTL seconds)."""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from glyphh_ada import links
from glyphh_ada.api.auth import AdaCaller, AdaWho
from glyphh_ada.api.body import bounded
from glyphh_ada.api.call import call
from glyphh_ada.api.files import base_of, link_for, link_url

router = APIRouter(tags=["jobs"], dependencies=[Depends(bounded)])


class NewExport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["jsonl", "ada_sqlite"] = Field(
        "jsonl",
        description="jsonl: a zip of the precedents, every spec version and what was learned; ada_sqlite: "
        "a kernel store a self-hosted runtime opens as precedents.sqlite",
    )


async def start(
    request: Request, who: AdaWho, name: str, kind: str, args: dict[str, Any] | None = None
) -> dict[str, Any]:
    return dict(await call(request, who, name, "job_start", {"kind": kind, "args": args or {}}))


def with_link(base: str, secret: str, who: AdaCaller, job: dict[str, Any]) -> dict[str, Any]:
    """A done export's job, with its download link at `base`, the Ada API's address (good for LINK_TTL from when it
    finished)."""
    if job["kind"] == "export" and job["state"] == "done":
        done = datetime.fromisoformat(job["finished_at"]).timestamp()
        link = link_for(who.org_id, job["model"], str(job["id"]), links.DOWN, done, job["result"]["filename"])
        job["download"] = link_url(base, secret, link)
    return job


@router.post("/v1/models/{name}/learn", operation_id="learnAdaModel", status_code=202)
async def learn(name: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """Learn each role's, value's, word's and pair's weight from the model's graded precedents, then calibrate."""
    return await start(request, who, name, "learn")


@router.post("/v1/models/{name}/calibrate", operation_id="calibrateAdaModel", status_code=202)
async def calibrate(name: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """Fit the temperature, so the probabilities mean what they say (or decide best, by the spec's costs)."""
    return await start(request, who, name, "calibrate")


@router.post("/v1/models/{name}/export", operation_id="exportAdaModel", status_code=202)
async def export(name: str, who: AdaWho, request: Request, body: NewExport | None = None) -> dict[str, Any]:
    """Everything of the model, as a job: once done, its job carries a one-hour download link."""
    return await start(request, who, name, "export", {"format": (body or NewExport()).format})


@router.get("/v1/jobs/{job_id}", operation_id="getAdaJob")
async def get_job(job_id: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """A job's state (awaiting its file, queued, running, done, failed), percent, stage (what it is doing now), and
    result or error; a done export's download link. A running job whose worker stopped and that no other took up is
    failed, E_JOB_STALLED."""
    job = dict(await call(request, who, "", "job", {"id": job_id}))
    return with_link(base_of(request), request.app.state.settings.secret_key, who, job)


@router.post("/v1/jobs/{job_id}/cancel", operation_id="cancelAdaJob")
async def cancel_job(job_id: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """Cancel a job. Not started yet, it ends at once; running, it stops at its next step, within seconds (its stage
    says `cancelling` until then). It ends failed, with E_CANCELLED saying what of its work stays. A job that has
    already ended is refused, 409 E_JOB_ENDED."""
    return dict(await call(request, who, "", "job_cancel", {"id": job_id}))
