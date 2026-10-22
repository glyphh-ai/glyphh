"""Imports (docs/specs/ada-cloud.md, section 6): a file of cases into a model, as a job.

`POST /v1/models/{name}/imports {format, mapping?, partial?, learn?}` answers the job, waiting for its file, and a
one-hour upload link to PUT the file to (`curl -T file <upload.url>`); a file of up to 5 MB can ride in the body
instead (`content`, or `content_base64` for an SQLite store), and the import is queued at once. Then
`GET /v1/models/{name}/imports/{id}` (or `GET /v1/jobs/{id}`) until it is done."""

import base64
import binascii
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from glyphh_ada import limits, links
from glyphh_ada.api.auth import AdaWho
from glyphh_ada.api.blobs import store
from glyphh_ada.api.body import bounded
from glyphh_ada.api.call import call
from glyphh_ada.api.files import link_for, queue, url
from glyphh_ada.errors import BadRequest, Refused
from glyphh_server.errors import Conflict, TooLarge

router = APIRouter(prefix="/v1/models/{name}/imports", tags=["imports"], dependencies=[Depends(bounded)])


class NewImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["jsonl", "csv", "ada_sqlite"] = Field(description="JSON Lines, CSV, or a kernel SQLite store")
    mapping: dict[str, str | None] | None = Field(
        None, description="CSV: {header: role path, outcome, outcome.<output>, ts or id; null skips the column}"
    )
    partial: bool = Field(False, description="Past the plan's cap, record new cases up to it and refuse the rest")
    learn: bool = Field(True, description="Learn and calibrate once at the end")
    content: str | None = Field(None, description="The file itself, as text, when it is small (5 MB)")
    content_base64: str | None = Field(None, description="The file itself, base64, when it is small (5 MB)")


def _content(body: NewImport) -> bytes | None:
    try:
        data = body.content.encode() if body.content is not None else None
        if body.content_base64 is not None:
            data = base64.b64decode(body.content_base64, validate=True)
    except binascii.Error:
        raise BadRequest("content_base64 is not base64.", reason="content_base64") from None
    if data is not None and len(data) > limits.IMPORT_BODY_MAX:
        raise TooLarge(f"A file in the body is at most {limits.IMPORT_BODY_MAX} bytes: use the upload link.")
    return data


async def _once(data: bytes) -> AsyncIterator[bytes]:
    yield data


@router.post("", operation_id="startAdaImport", status_code=202)
async def start(name: str, body: NewImport, who: AdaWho, request: Request) -> dict[str, Any]:
    """An import: the job, and its upload link (or, with the file in the body, the job queued)."""
    data = _content(body)
    args = body.model_dump(exclude={"content", "content_base64"}, exclude_none=True)
    job = dict(await call(request, who, name, "import_start", args))
    link = link_for(who.org_id, name, str(job["id"]), links.UP)
    if data is None:
        return {**job, "upload": url(request, link)}
    state = request.app.state
    try:
        await store(state.engine, link.org, link.job, _once(data), state.settings.ada_import_bytes)
    except Conflict:  # the same request again (its Idempotency-Key): the import as it stands
        return dict(await call(request, who, "", "job", {"id": link.job}))
    return await queue(request, link)


@router.get("/{job_id}", operation_id="getAdaImport")
async def get_import(name: str, job_id: str, who: AdaWho, request: Request) -> dict[str, Any]:
    """An import's state, percent, and its result: rows, recorded, added, replaced, refused (the first named)."""
    job = dict(await call(request, who, "", "job", {"id": job_id}))
    if job["kind"] != "import" or job["model"] != name:
        raise Refused("E_JOB_MISSING", f"No import {job_id} of {name}.", 404, job=job_id)
    return job
