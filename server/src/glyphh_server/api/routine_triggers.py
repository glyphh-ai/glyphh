"""The routine triggers a person gave Glyphh, so the Cloud can start their Claude routines on a program's events."""

import uuid

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from glyphh_server.api.auth import Caller, Conn
from glyphh_server.ops import routine_triggers
from glyphh_server.ops.routine_triggers import FIRE_URL, TriggerView

router = APIRouter(prefix="/v1/routine-triggers", tags=["routine triggers"])


class NewTrigger(BaseModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S")
    fire_url: str = Field(
        pattern=FIRE_URL,
        max_length=200,
        description="The routine's API trigger: https://api.anthropic.com/v1/claude_code/routines/<id>/fire",
    )
    token: str = Field(min_length=1, max_length=512, description="The trigger's token: kept encrypted, never shown")
    program_id: uuid.UUID | None = Field(None, description="The program whose events fire it; none for any")


@router.get("", operation_id="listRoutineTriggers")
async def list_triggers(caller: Caller, conn: Conn) -> list[TriggerView]:
    """The person's routine triggers, never their tokens."""
    return await routine_triggers.list_triggers(conn, caller)


@router.post("", operation_id="createRoutineTrigger", status_code=201)
async def create_trigger(body: NewTrigger, caller: Caller, conn: Conn, request: Request) -> TriggerView:
    """Give Glyphh a routine's API trigger. Its token starts that routine only; it is not a Claude login."""
    key = request.app.state.secrets_key
    name = body.name.strip()
    return await routine_triggers.create_trigger(conn, caller, key, name, body.fire_url, body.token, body.program_id)


@router.delete("/{trigger_id}", operation_id="deleteRoutineTrigger", status_code=204)
async def delete_trigger(trigger_id: uuid.UUID, caller: Caller, conn: Conn) -> Response:
    await routine_triggers.delete_trigger(conn, caller, trigger_id)
    return Response(status_code=204)
