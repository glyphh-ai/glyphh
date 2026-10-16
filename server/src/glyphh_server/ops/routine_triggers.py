"""The routine triggers a person gave Glyphh: a Claude routine's API trigger (its fire URL and token) that the Cloud
fires on a model's events. The token is sealed at rest and never shown again; a list shows everything else."""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from glyphh_server.errors import NotFound
from glyphh_server.models import Model, RoutineTrigger
from glyphh_server.ops import vault
from glyphh_server.ops.auth.principal import Principal

# Anthropic's routine fire endpoint, the only address a trigger may name.
FIRE_URL: str = r"^https://api\.anthropic\.com/v1/claude_code/routines/[A-Za-z0-9_-]{1,128}/fire$"


class TriggerView(BaseModel):
    id: uuid.UUID
    name: str
    fire_url: str
    model_id: uuid.UUID | None
    status: str
    last_fired_at: datetime | None
    created_at: datetime


_COLUMNS = (
    RoutineTrigger.id,
    RoutineTrigger.name,
    RoutineTrigger.fire_url,
    RoutineTrigger.model_id,
    RoutineTrigger.status,
    RoutineTrigger.last_fired_at,
    RoutineTrigger.created_at,
)


def sealed_for(user_id: uuid.UUID, fire_url: str) -> str:
    """What a trigger's sealed token is bound to: its owner and its fire URL."""
    return f"routine_trigger:{user_id}:{fire_url}"


async def list_triggers(conn: AsyncConnection, who: Principal) -> list[TriggerView]:
    rows = await conn.execute(
        select(*_COLUMNS).where(RoutineTrigger.user_id == who.user_id).order_by(RoutineTrigger.created_at)
    )
    return [TriggerView(**r._mapping) for r in rows]


async def create_trigger(
    conn: AsyncConnection,
    who: Principal,
    key: bytes | None,
    name: str,
    fire_url: str,
    token: str,
    model_id: uuid.UUID | None,
) -> TriggerView:
    token_enc = vault.seal(key, token, sealed_for(who.user_id, fire_url))
    if model_id is not None:
        mine = select(Model.id).where(Model.id == model_id, Model.user_id == who.user_id)
        if (await conn.execute(mine)).first() is None:
            raise NotFound("You have no such model.", model_id=str(model_id))
    values = {"user_id": who.user_id, "model_id": model_id, "name": name, "fire_url": fire_url}
    made = insert(RoutineTrigger).values(**values, token_enc=token_enc).returning(*_COLUMNS)
    return TriggerView(**(await conn.execute(made)).one()._mapping)


async def delete_trigger(conn: AsyncConnection, who: Principal, trigger_id: uuid.UUID) -> None:
    gone = await conn.execute(
        delete(RoutineTrigger).where(RoutineTrigger.id == trigger_id, RoutineTrigger.user_id == who.user_id)
    )
    if gone.rowcount == 0:
        raise NotFound("You have no such routine trigger.", trigger_id=str(trigger_id))
