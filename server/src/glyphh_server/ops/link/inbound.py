"""What a rrotor's messages change. Each is applied in one transaction as the runtime's org, by the session.

A result updates its run (status, seconds, ended once final), and a step that needs approval waits in `approvals`.
An event is recorded, and fires the routine trigger it names when that trigger is the model owner's and for that
model (or for any). A deployed version, recorded when new (ops/link/reports.py), becomes the model's active one on
that runtime. A result or event is
applied once: its `seq` must be past the runtime's last applied one, else it is a replay, acked and skipped."""

import json
import logging
import uuid

from redis.asyncio import Redis
from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.models import Deployment, Model, ModelEvent, ModelVersion, RoutineTrigger, Rrotor, Run
from glyphh_server.obs.logs import fields
from glyphh_server.ops import nodes
from glyphh_server.ops.approvals import ask_approval
from glyphh_server.ops.link import reports
from glyphh_server.ops.link.calls import hold_run
from glyphh_server.ops.link.presence import Runtime
from glyphh_server.ops.link.protocol import FINAL, Deployed, Event, Hello, Result
from glyphh_server.ops.routines import Routines, fire_routine

log = logging.getLogger("glyphh.link")


async def first_time(conn: AsyncConnection, runtime: Runtime, seq: int) -> bool:
    """Whether this sequence number is new for this runtime; taking it is part of applying the message."""
    took = update(Rrotor).where(Rrotor.id == runtime.id, Rrotor.seq < seq).values(seq=seq).returning(Rrotor.id)
    return (await conn.execute(took)).first() is not None


async def apply_result(conn: AsyncConnection, redis: Redis, runtime: Runtime, message: Result) -> None:
    outcome = message.result
    await hold_run(conn, message.run_id)
    values: dict[str, object] = {"status": outcome.status, "seconds": message.seconds}
    if outcome.status in FINAL:
        values["ended_at"] = func.now()
    mine = update(Run).where(Run.id == message.run_id, Run.rrotor_id == runtime.id).values(**values)
    if (await conn.execute(mine.returning(Run.id))).first() is None:
        log.warning("result for a run this runtime does not have", extra=fields(run_id=str(message.run_id)))
        return
    if outcome.status == "needs_approval":
        await ask_approval(conn, redis, message.run_id, str(outcome.step), str(outcome.prompt))


async def _model(conn: AsyncConnection, runtime: Runtime, name: str) -> uuid.UUID | None:
    """The runtime owner's model of that name (the newest, should a name have been used twice)."""
    found = select(Model.id).where(Model.user_id == runtime.user_id, Model.name == name)
    return (await conn.execute(found.order_by(Model.created_at.desc()).limit(1))).scalar()


async def _owners_trigger(conn: AsyncConnection, runtime: Runtime, trigger: uuid.UUID, model_id: uuid.UUID) -> bool:
    found = select(RoutineTrigger.id).where(
        RoutineTrigger.id == trigger,
        RoutineTrigger.user_id == runtime.user_id,
        or_(RoutineTrigger.model_id.is_(None), RoutineTrigger.model_id == model_id),
    )
    return (await conn.execute(found)).first() is not None


async def apply_event(
    conn: AsyncConnection, routines: Routines, key: bytes | None, runtime: Runtime, message: Event
) -> None:
    model_id = await _model(conn, runtime, message.model)
    if model_id is None:
        log.warning("event for a model Glyphh has no record of", extra=fields(model=message.model))
        return
    if message.trigger is not None and await _owners_trigger(conn, runtime, message.trigger, model_id):
        text = json.dumps({"model": message.model, "event": message.kind, "data": message.data})
        fired = await fire_routine(conn, routines, key, message.trigger, text, model_id=model_id, kind=message.kind)
        if fired.outcome == "fired":
            return  # recorded with the trigger it fired and the session it started
    await conn.execute(insert(ModelEvent).values(model_id=model_id, kind=message.kind))


async def apply_deployed(conn: AsyncConnection, runtime: Runtime, message: Deployed) -> None:
    model_id, version_id = await reports.version_for(conn, runtime, message)
    siblings = select(ModelVersion.id).where(ModelVersion.model_id == model_id)
    await conn.execute(
        update(Deployment)
        .where(Deployment.rrotor_id == runtime.id, Deployment.model_version_id.in_(siblings))
        .values(active=False)
    )
    made = upsert(Deployment).values(rrotor_id=runtime.id, model_version_id=version_id, active=True)
    await conn.execute(
        made.on_conflict_do_update(
            index_elements=["rrotor_id", "model_version_id"], set_={"active": True, "deployed_at": func.now()}
        )
    )


async def record_hello(engine: AsyncEngine, runtime: Runtime, hello: Hello) -> None:
    """The versions a hello says are active, recorded as a `deployed` of each is, in one transaction as the owner:
    a model deployed while the link was down is never missed; and the node it is, when it says (ops/nodes.py)."""
    async with engine.begin() as conn:
        await tenancy.enter(conn, runtime.org_id)
        for version in hello.deployed:
            await apply_deployed(conn, runtime, Deployed(type="deployed", **version.model_dump()))
        if hello.node_id is not None:
            said = {"cluster_id": hello.cluster_id, "role": hello.role, "version": hello.version}
            await nodes.record(conn, runtime.id, hello.node_id, said)
