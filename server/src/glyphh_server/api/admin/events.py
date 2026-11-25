"""The server's own errors and warnings (ops events), for staff: listed with filters, and acknowledged one by one or
every open one of a severity and kind at once."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from glyphh_server.api.admin.deps import Staff
from glyphh_server.errors import NotFound
from glyphh_server.obs import events_store
from glyphh_server.obs.events_store import OpsEventPage

router = APIRouter()

Severity = Literal["warning", "error", "critical"]


class AckAll(BaseModel):
    severity: Severity | None = None
    kind: str | None = Field(None, max_length=40)


class Acknowledged(BaseModel):
    acknowledged: int


@router.get("/events", operation_id="adminEvents")
async def list_events(
    staff: Staff,
    severity: Severity | None = None,
    kind: str | None = None,
    open_only: bool = False,
    before: datetime | None = None,
) -> OpsEventPage:
    return await events_store.listing(staff.conn, severity, kind, open_only, before)


@router.post("/events/{event_id}/ack", operation_id="adminAckEvent")
async def ack_event(event_id: uuid.UUID, staff: Staff) -> Acknowledged:
    done = await events_store.acknowledge(staff.conn, staff.who.email, event_id=event_id)
    if done == 0:
        raise NotFound("There is no such open event.", event_id=str(event_id))
    return Acknowledged(acknowledged=done)


@router.post("/events/ack", operation_id="adminAckEvents")
async def ack_events(body: AckAll, staff: Staff) -> Acknowledged:
    """Every open event of this severity and kind (either left out: any)."""
    done = await events_store.acknowledge(staff.conn, staff.who.email, severity=body.severity, kind=body.kind)
    await staff.note(acknowledged=done)
    return Acknowledged(acknowledged=done)
