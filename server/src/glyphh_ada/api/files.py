"""Files by signed link, with no key: the link is the credential (links.py), for limits.LINK_TTL seconds.

- `PUT /v1/uploads/{link}`: an import's file, streamed in (up to GLYPHH_ADA_IMPORT_BYTES), which queues the import:
  `curl -T cases.jsonl <upload_url>`. Once the import has started, its link takes no other file (409).
- `GET /v1/downloads/{link}`: an export's archive, streamed out, while its link works and the file is kept."""

import time
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from glyphh_ada import limits, links
from glyphh_ada.api import blobs
from glyphh_ada.api.auth import AdaCaller
from glyphh_ada.api.call import send

router = APIRouter(tags=["files"])
TYPES: dict[str, str] = {".zip": "application/zip", ".sqlite": "application/vnd.sqlite3"}


def base_of(request: Request) -> str:
    """This host's address, by the scheme the caller used (Fly's proxy says it: X-Forwarded-Proto)."""
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{scheme}://{request.url.netloc}"


def link_url(base: str, secret: str, link: links.Link) -> dict[str, Any]:
    """The link as a URL at the Ada API's address, and when it stops working."""
    path = "uploads" if link.kind == links.UP else "downloads"
    return {"url": f"{base}/v1/{path}/{links.sign(secret, link)}", "expires_at": link.expires}


def link_for(org: uuid.UUID, model: str, job: str, kind: str, since: float | None = None, name: str = "") -> links.Link:
    return links.Link(str(org), model, job, kind, int((since or time.time()) + limits.LINK_TTL), name)


async def queue(state: Any, link: links.Link) -> dict[str, Any]:
    """The import's file is in: the worker queues its job."""
    who = AdaCaller(uuid.UUID(link.org), uuid.UUID(int=0), 1.0)
    return dict((await send(state, who, link.model, "import_go", {"job": link.job}))[0])


@router.put("/v1/uploads/{token}", operation_id="uploadAdaImport", status_code=202)
async def upload(token: str, request: Request) -> dict[str, Any]:
    """An import's file, by its upload link: stored whole, then the import is queued. Answers the import's job."""
    state = request.app.state
    link = links.check(state.settings.secret_key, token, links.UP)
    await blobs.store(state.engine, link.org, link.job, request.stream(), state.settings.ada_import_bytes)
    return await queue(state, link)


@router.get("/v1/downloads/{token}", operation_id="downloadAdaExport")
async def download(token: str, request: Request) -> StreamingResponse:
    """An export's archive, by its download link."""
    state = request.app.state
    link = links.check(state.settings.secret_key, token, links.DOWN)
    await blobs.exists(state.engine, link.org, link.job)
    kind = TYPES.get(link.name[link.name.rfind(".") :], "application/octet-stream")
    headers = {"content-disposition": f'attachment; filename="{link.name}"'}
    return StreamingResponse(blobs.pieces(state.engine, link.org, link.job), media_type=kind, headers=headers)
