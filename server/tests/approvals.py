"""A person's run, made straight in the database, waiting at a step that needs approval."""

import asyncio
import uuid

from redis.asyncio import Redis
from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Model, ModelVersion, Rrotor, Run
from tests.db.helpers import Person

SHA: str = "0123456789abcdef0123456789abcdef01234567"


async def a_run(engine: AsyncEngine, who: Person, model: str = "leads") -> uuid.UUID:
    """A run of a new model of this person's, on their install's local runtime, waiting for an approval."""
    async with engine.begin() as conn:
        rrotor = {"user_id": who.user_id, "mode": "local", "install_id": who.install_id, "state": "stopped"}
        made = upsert(Rrotor).values(**rrotor, token_hash=uuid.uuid4().hex)
        made = made.on_conflict_do_update(index_elements=[Rrotor.install_id], set_={"state": "stopped"})
        made = made.returning(Rrotor.id)
        rrotor_id = (await conn.execute(made)).scalar_one()
        values = {"user_id": who.user_id, "org_id": who.org_id, "name": model}
        model_id = (await conn.execute(insert(Model).values(values).returning(Model.id))).scalar_one()
        values = {"model_id": model_id, "version": 1, "commit_sha": SHA, "manifest": {}}
        version_id = (await conn.execute(insert(ModelVersion).values(values).returning(ModelVersion.id))).scalar()
        values = {
            "model_version_id": version_id,
            "rrotor_id": rrotor_id,
            "function": "start",
            "status": "needs_approval",
        }
        return (await conn.execute(insert(Run).values(**values, caller="claude").returning(Run.id))).scalar_one()


async def listeners(redis: Redis, channel: str, expected: int) -> int:
    """How many connections listen on a channel, given a moment to settle on the expected count: Redis drops a
    closed connection's subscriptions a beat after it closes."""
    for _ in range(50):
        count = dict(await redis.pubsub_numsub(channel))[channel]
        if count == expected:
            break
        await asyncio.sleep(0.02)
    return count


async def runtime_of(engine: AsyncEngine, run_id: uuid.UUID) -> uuid.UUID:
    async with engine.connect() as conn:
        return (await conn.execute(select(Run.rrotor_id).where(Run.id == run_id))).scalar_one()
