"""The Cloud firing a routine trigger: the call Anthropic documents, the session it started kept on a program event,
a refused token marking the trigger broken, and every other failure an outcome, never a crash."""

import json
import uuid

import httpx
import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Invalid, NotFound
from glyphh_server.models import Program, ProgramEvent, RoutineTrigger
from glyphh_server.ops import vault
from glyphh_server.ops.routine_triggers import sealed_for
from glyphh_server.ops.routines import BETA, VERSION, Fired, Routines, fire_routine
from tests.conftest import SETTINGS
from tests.db.helpers import person
from tests.fakes import FakeRoutines, fake_http

FIRE: str = "https://api.anthropic.com/v1/claude_code/routines/trig_01XYZ/fire"
KEY: bytes | None = vault.load_key(SETTINGS)


async def _trigger(engine: AsyncEngine, for_program: bool = True) -> tuple[uuid.UUID, uuid.UUID]:
    ada = await person(engine, "Pro")
    async with engine.begin() as conn:
        values = {"user_id": ada.user_id, "org_id": ada.org_id, "name": "daily_sales"}
        program_id = (await conn.execute(insert(Program).values(values).returning(Program.id))).scalar_one()
        sealed = vault.seal(KEY, "routine-token", sealed_for(ada.user_id, FIRE))
        trigger = {"user_id": ada.user_id, "name": "Sales", "fire_url": FIRE, "token_enc": sealed}
        made = insert(RoutineTrigger).values(**trigger, program_id=program_id if for_program else None)
        trigger_id = (await conn.execute(made.returning(RoutineTrigger.id))).scalar_one()
    return trigger_id, program_id


async def _fire(engine: AsyncEngine, fake: FakeRoutines, trigger_id: uuid.UUID, program_id: uuid.UUID) -> Fired:
    async with engine.begin() as conn:
        routines = Routines(fake_http(routines=fake))
        return await fire_routine(
            conn, routines, KEY, trigger_id, '{"event": "done"}', program_id=program_id, kind="done"
        )


async def _state(engine: AsyncEngine, trigger_id: uuid.UUID) -> tuple[object, ...]:
    async with engine.connect() as conn:
        row = (await conn.execute(select(RoutineTrigger).where(RoutineTrigger.id == trigger_id))).one()
        events = (await conn.execute(select(ProgramEvent).where(ProgramEvent.routine_trigger_id == trigger_id))).all()
    return row.status, row.last_fired_at, events


async def test_a_fire_is_the_documented_call_and_its_session_is_kept(engine: AsyncEngine) -> None:
    trigger_id, program_id = await _trigger(engine)
    fake = FakeRoutines()
    fired = await _fire(engine, fake, trigger_id, program_id)
    assert fired == Fired("fired", "https://claude.ai/code/session_fake")
    sent = fake.calls[0]
    assert (sent.method, str(sent.url)) == ("POST", FIRE)
    assert sent.headers["authorization"] == "Bearer routine-token"
    assert (sent.headers["anthropic-beta"], sent.headers["anthropic-version"]) == (BETA, VERSION)
    assert sent.headers["content-type"] == "application/json"
    assert json.loads(sent.content) == {"text": '{"event": "done"}'}
    status, last_fired_at, events = await _state(engine, trigger_id)
    assert status == "ok" and last_fired_at is not None
    assert [(e.program_id, e.kind, e.session_url) for e in events] == [
        (program_id, "done", "https://claude.ai/code/session_fake")
    ]


async def test_a_refused_token_breaks_the_trigger_and_it_is_not_fired_again(engine: AsyncEngine) -> None:
    trigger_id, program_id = await _trigger(engine, for_program=False)
    fake = FakeRoutines()
    fake.reply = httpx.Response(401, json={"error": {"type": "authentication_error"}})
    assert await _fire(engine, fake, trigger_id, program_id) == Fired("broken")
    assert await _fire(engine, fake, trigger_id, program_id) == Fired("broken")
    assert len(fake.calls) == 1
    status, last_fired_at, events = await _state(engine, trigger_id)
    assert (status, last_fired_at, events) == ("broken", None, [])


@pytest.mark.parametrize(
    "reply",
    [
        httpx.Response(429, json={"error": {"type": "rate_limit_error"}}),
        httpx.Response(500, text="down"),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json=["not", "an", "object"]),
        httpx.ConnectError("unreachable"),
    ],
)
async def test_any_other_answer_is_a_failed_fire_and_nothing_is_recorded(
    engine: AsyncEngine, reply: httpx.Response | Exception
) -> None:
    trigger_id, program_id = await _trigger(engine)
    fake = FakeRoutines()
    fake.reply = reply
    assert await _fire(engine, fake, trigger_id, program_id) == Fired("failed")
    assert await _state(engine, trigger_id) == ("ok", None, [])


async def test_an_answer_without_a_session_still_records_the_event(engine: AsyncEngine) -> None:
    trigger_id, program_id = await _trigger(engine)
    fake = FakeRoutines()
    fake.reply = httpx.Response(200, json={"type": "routine_fire", "claude_code_session_url": 7})
    assert await _fire(engine, fake, trigger_id, program_id) == Fired("fired", None)
    assert [e.session_url for e in (await _state(engine, trigger_id))[2]] == [None]


async def test_an_unknown_trigger_or_another_programs_is_refused(engine: AsyncEngine) -> None:
    trigger_id, _ = await _trigger(engine)
    fake = FakeRoutines()
    with pytest.raises(NotFound):
        await _fire(engine, fake, uuid.uuid4(), uuid.uuid4())
    with pytest.raises(Invalid, match="another program"):
        await _fire(engine, fake, trigger_id, uuid.uuid4())
    assert fake.calls == []
