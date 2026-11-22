"""Recents (docs/specs/bots.md, 11): the org's runs in one list, a bot's own and a crew's alike, with the count of
those that wait on a person; a person's own pin and archive on a run; a run deleted."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops.bots import recents
from glyphh_server.ops.bots.recents import Asked, Mark, Recent, Recents

router = APIRouter(prefix="/v1/recents", tags=["bots"])


@router.get("", operation_id="listRecents")
async def list_recents(
    caller: Caller,
    conn: Conn,
    q: Annotated[str, Query(max_length=200, description="Found in the task, a bot's name or the workspace")] = "",
    waiting: Annotated[bool, Query(description="Only the runs that wait on a person")] = False,
    archived: Annotated[bool, Query(description="Only the runs this person archived (else they are left out)")] = False,
    pinned: Annotated[bool, Query(description="Only the runs this person pinned")] = False,
    cursor: Annotated[datetime | None, Query(description="The last page's next_cursor")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> Recents:
    """The org's runs, a bot's and a crew's alike, the newest first; `needs_you` counts those waiting on a person."""
    asked = Asked(q=q, waiting=waiting, archived=archived, pinned=pinned, cursor=cursor, limit=limit)
    return await recents.listing(conn, caller, asked)


@router.post("/{run_id}/{how}", operation_id="markRecent")
async def mark_recent(run_id: uuid.UUID, how: Mark, caller: Caller, conn: Conn) -> Recent:
    """The person's own mark on a run: pin, unpin, archive or unarchive."""
    return await recents.mark(conn, caller, run_id, how)


@router.delete("/{run_id}", operation_id="deleteRecent", status_code=204)
async def delete_recent(run_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    """The run deleted for the whole org, with its turns (pull requests stay on GitHub); 409 run_live while it is
    going or waiting: cancel it first."""
    await recents.remove(conn, caller, run_id)
    return Response(status_code=204)
