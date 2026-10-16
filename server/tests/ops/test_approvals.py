"""Asking for an approval, the entry point the runtime's link calls: the row is kept and the person's open Claudes hear
it on their Redis channel. The stream's heartbeat, and the email seam that is not built."""

import json
import uuid

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import NotFound, Unavailable
from glyphh_server.models import Approval
from glyphh_server.ops import approval_stream
from glyphh_server.ops.approvals import ask_approval, channel, email_approval
from glyphh_server.ops.auth.principal import Principal
from tests.approvals import a_run, listeners
from tests.db.helpers import person


async def test_asking_keeps_the_step_waiting_and_signals_the_persons_channel(engine: AsyncEngine, redis: Redis) -> None:
    ada = await person(engine)
    run_id = await a_run(engine, ada, model="daily_sales")
    async with redis.pubsub() as pubsub:
        await pubsub.subscribe(channel(ada.user_id))
        async with engine.begin() as conn:
            await tenancy.enter(conn, ada.org_id)
            asked = await ask_approval(conn, redis, run_id, "post", "Post the report to #sales?")
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5)
        message = message or await pubsub.get_message(ignore_subscribe_messages=True, timeout=5)
    assert asked.watched is True
    view = asked.approval
    assert (view.model, view.step, view.prompt) == ("daily_sales", "post", "Post the report to #sales?")
    assert message is not None and json.loads(message["data"]) == {
        "event": "approval",
        "data": view.model_dump(mode="json"),
    }
    async with engine.connect() as conn:
        row = (await conn.execute(select(Approval).where(Approval.id == view.id))).one()
    assert (row.run_id, row.answer, row.notified_at, row.answered_at) == (run_id, None, None, None)


async def test_nobody_watching_is_said_and_only_a_known_run_of_ones_org_is_asked(
    engine: AsyncEngine, redis: Redis
) -> None:
    ada, eve = await person(engine), await person(engine)
    run_id = await a_run(engine, ada)
    async with engine.begin() as conn:
        assert (await ask_approval(conn, redis, run_id, "post", "Post it?")).watched is False
    for org_id, run in ((ada.org_id, uuid.uuid4()), (eve.org_id, run_id)):
        with pytest.raises(NotFound):
            async with engine.begin() as conn:
                await tenancy.enter(conn, org_id)
                await ask_approval(conn, redis, run, "post", "Post it?")


async def test_an_idle_stream_sends_a_heartbeat_and_gives_its_connection_back(
    engine: AsyncEngine, redis: Redis
) -> None:
    ada = await person(engine)
    who = Principal(user_id=ada.user_id, org_id=ada.org_id, role="admin", install_id=ada.install_id)
    events = approval_stream.stream(engine, redis, who, heartbeat=0.05)
    assert await anext(events) == ": heartbeat\n\n"
    assert await listeners(redis, channel(ada.user_id), 1) == 1
    await events.aclose()
    assert await listeners(redis, channel(ada.user_id), 0) == 0


async def test_the_approval_email_is_not_built_and_says_so(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        with pytest.raises(Unavailable, match="no mail provider"):
            await email_approval(conn, uuid.uuid4())
