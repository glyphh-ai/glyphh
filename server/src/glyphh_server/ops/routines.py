"""The Cloud starting a person's Claude routine through its API trigger, with a model's event as the text.

Anthropic answers with the Claude session the fire started; it is recorded on a model event so the person can
open it. A 401 means the person regenerated or deleted the token: the trigger is marked broken, and is not fired
again until they give a new one. Nothing here raises for Anthropic's answer: the outcome says what happened."""

import logging
import uuid
from dataclasses import dataclass
from typing import Literal

import httpx
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import Invalid, NotFound
from glyphh_server.models import ModelEvent, RoutineTrigger
from glyphh_server.obs.logs import fields
from glyphh_server.ops import vault
from glyphh_server.ops.routine_triggers import sealed_for

log = logging.getLogger("glyphh.routines")

# The routines API is a research preview: one dated beta header, pinned, moved deliberately.
BETA: str = "experimental-cc-routine-2026-04-01"
VERSION: str = "2023-06-01"


class Routines:
    """Anthropic's routine fire endpoint, over the server's HTTP client (faked in tests)."""

    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def fire(self, fire_url: str, token: str, text: str) -> httpx.Response:
        headers = {"authorization": f"Bearer {token}", "anthropic-beta": BETA, "anthropic-version": VERSION}
        return await self.http.post(fire_url, json={"text": text}, headers=headers)


@dataclass(frozen=True, slots=True)
class Fired:
    outcome: Literal["fired", "broken", "failed"]
    session_url: str | None = None


async def fire_routine(
    conn: AsyncConnection,
    routines: Routines,
    key: bytes | None,
    trigger_id: uuid.UUID,
    text: str,
    *,
    model_id: uuid.UUID,
    kind: str,
) -> Fired:
    """Fire this trigger for this model's event (kind), with `text` as the routine's payload."""
    trigger = (await conn.execute(select(RoutineTrigger).where(RoutineTrigger.id == trigger_id))).first()
    if trigger is None:
        raise NotFound("There is no such routine trigger.", trigger_id=str(trigger_id))
    if trigger.model_id not in (None, model_id):
        raise Invalid("This routine trigger is for another model.", trigger_id=str(trigger_id))
    if trigger.status == "broken":
        return Fired("broken")
    token = vault.unseal(key, trigger.token_enc, sealed_for(trigger.user_id, trigger.fire_url))
    try:
        res = await routines.fire(trigger.fire_url, token, text)
        answer = res.json() if res.is_success else None
    except (httpx.HTTPError, ValueError) as err:
        log.warning("routine fire failed", extra=fields(trigger=str(trigger_id), error=repr(err)))
        return Fired("failed")
    if res.status_code == httpx.codes.UNAUTHORIZED:
        await conn.execute(update(RoutineTrigger).where(RoutineTrigger.id == trigger_id).values(status="broken"))
        log.info("routine trigger broken", extra=fields(trigger=str(trigger_id)))
        return Fired("broken")
    if not isinstance(answer, dict):
        log.warning("routine fire refused", extra=fields(trigger=str(trigger_id), status=res.status_code))
        return Fired("failed")
    return await _record(conn, trigger_id, model_id, kind, answer.get("claude_code_session_url"))


async def _record(conn: AsyncConnection, trigger_id: uuid.UUID, model_id: uuid.UUID, kind: str, url: object) -> Fired:
    session_url = url if isinstance(url, str) else None
    await conn.execute(update(RoutineTrigger).where(RoutineTrigger.id == trigger_id).values(last_fired_at=func.now()))
    values = {"model_id": model_id, "routine_trigger_id": trigger_id, "kind": kind, "session_url": session_url}
    await conn.execute(insert(ModelEvent).values(**values))
    return Fired("fired", session_url)
