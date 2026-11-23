"""A bot's schedule: chosen in plain words, its next run worked out in the person's time zone (a month's day past its
end its last day), kept on the bot, said back as `Next run Mon 9:00`, and fired by the minute tick once when due,
however many ticks were missed, skipping a bot whose run is still live."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Bot, BotRun
from glyphh_server.ops import tend
from glyphh_server.ops.bots import due
from glyphh_server.ops.bots.schedule import Schedule, label, next_after, summary
from glyphh_server.ops.link.hub import Hub
from tests.bots.agents import play
from tests.bots.conftest import BOTS, SEND, Served, connected, made_bot
from tests.bots.remote import logged
from tests.connector import granted, tool
from tests.db.helpers import Person, person

CHICAGO: str = "America/Chicago"
SAT: datetime = datetime(2026, 11, 21, 14, 0, tzinfo=UTC)  # Saturday 8:00 in Chicago


def at(every: str, **over: Any) -> datetime | None:
    return next_after(Schedule(every=every, timezone=CHICAGO, **over), SAT)  # type: ignore[arg-type]


def test_each_schedule_finds_its_next_run_in_the_persons_zone() -> None:
    assert at("off") is None
    assert next_after(Schedule(every="hour"), datetime(2026, 11, 21, 10, 15, tzinfo=UTC)) == datetime(
        2026, 11, 21, 11, 0, tzinfo=UTC
    )
    assert at("day") == datetime(2026, 11, 21, 15, 0, tzinfo=UTC)  # 9:00 in Chicago, later today
    assert at("day", at="07:30") == datetime(2026, 11, 22, 13, 30, tzinfo=UTC)  # gone today: tomorrow
    assert at("weekdays") == datetime(2026, 11, 23, 15, 0, tzinfo=UTC)  # a Saturday: Monday
    assert at("week", weekday=2, at="18:05") == datetime(2026, 11, 26, 0, 5, tzinfo=UTC)  # Wednesday's evening
    assert at("month", day=31) == datetime(2026, 11, 30, 15, 0, tzinfo=UTC)  # November ends on the 30th
    assert at("month", day=3) == datetime(2026, 12, 3, 15, 0, tzinfo=UTC)
    summer = next_after(Schedule(every="day", timezone=CHICAGO), datetime(2026, 7, 1, 12, tzinfo=UTC))
    assert summer == datetime(2026, 7, 1, 14, 0, tzinfo=UTC)  # daylight time: an hour earlier in UTC


def test_a_schedule_is_said_in_plain_words_and_its_next_run_by_day_and_time() -> None:
    said = [summary(Schedule(every=e, at="09:05", weekday=4, day=15)) for e in ("off", "hour", "day", "weekdays")]
    assert said == ["Off", "Every hour", "Every day at 9:05", "Weekdays at 9:05"]
    assert summary(Schedule(every="week", weekday=4, at="17:00")) == "Every Friday at 17:00"
    assert summary(Schedule(every="month", day=15)) == "Every month on day 15 at 9:00"
    kept = Schedule(every="day", timezone=CHICAGO)
    assert label(kept, datetime(2026, 11, 23, 15, 0, tzinfo=UTC), SAT) == "Mon 9:00"
    assert label(kept, datetime(2026, 12, 15, 15, 0, tzinfo=UTC), SAT) == "Tue 15 Dec 9:00"
    assert label(kept, None) == ""


def test_a_time_zone_that_is_not_one_is_refused() -> None:
    for zone in ("Mars/Olympus", "", "../etc/passwd", "America"):
        with pytest.raises(ValidationError, match="not a time zone"):
            Schedule(every="day", timezone=zone)


WEEKDAYS: dict[str, Any] = {"every": "weekdays", "at": "09:00", "timezone": CHICAGO, "input": "is:unread"}


@pytest.fixture(autouse=True)
async def quiet(engine: AsyncEngine) -> AsyncIterator[None]:
    """After each test, no bot of the session's database is due: the next test's tick fires only its own."""
    yield
    async with engine.begin() as conn:
        await conn.execute(update(Bot).values(next_run_at=None))


async def _due(engine: AsyncEngine, who: Person, ago: timedelta) -> None:
    """The org's bots that are on a schedule (never its orchestrator, which is on none) were due `ago`."""
    mine = (Bot.org_id == who.org_id, Bot.next_run_at.is_not(None))
    async with engine.begin() as conn:
        await conn.execute(update(Bot).where(*mine).values(next_run_at=datetime.now(UTC) - ago))


async def _runs(engine: AsyncEngine, who: Person) -> list[Any]:
    async with engine.connect() as conn:
        return list(await conn.execute(select(BotRun).where(BotRun.org_id == who.org_id).order_by(BotRun.created_at)))


async def test_a_bot_keeps_its_schedule_and_says_its_next_run(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    bot = await made_bot(served, ada)
    assert bot["schedule"]["every"] == "off" and bot["next_run_at"] is None and bot["next_run"] == ""
    assert bot["schedule_summary"] == "Off" and bot["runs_on"] is None
    res = await served.http.patch("/v1/bots/inbox-cat", json={"schedule": WEEKDAYS}, headers=ada.headers)
    assert res.status_code == 200, res.text
    kept = res.json()
    assert kept["schedule"] == {**WEEKDAYS, "weekday": 0, "day": 1} and kept["schedule_summary"] == "Weekdays at 9:00"
    assert kept["next_run_at"] and kept["next_run"].endswith(" 9:00")
    res = await served.http.patch("/v1/bots/inbox-cat", json={"summary": "Mail"}, headers=ada.headers)
    assert res.json()["next_run_at"] == kept["next_run_at"]  # the schedule left alone: so is its next run
    bad = {"schedule": {**WEEKDAYS, "timezone": "Mars/Olympus"}}
    assert (await served.http.patch("/v1/bots/inbox-cat", json=bad, headers=ada.headers)).status_code == 422
    res = await served.http.patch("/v1/bots/inbox-cat", json={"schedule": {"every": "off"}}, headers=ada.headers)
    assert res.json()["next_run_at"] is None and res.json()["next_run"] == ""


async def test_a_bot_is_made_on_a_schedule_and_the_connector_says_its_next_run(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    made = await made_bot(served, ada, schedule={"every": "hour"})
    assert made["schedule_summary"] == "Every hour" and made["next_run_at"]
    _, auth = await granted(engine, ada)
    said = (await tool(served.http, auth, "bot", slug="inbox-cat"))["content"][0]["text"]
    assert "schedule Every hour, Next run " in said and "runs on Glyphh cloud" in said
    changed = await tool(served.http, auth, "bot_update", slug="inbox-cat", schedule={"every": "day", "at": "07:15"})
    assert changed["structuredContent"]["schedule_summary"] == "Every day at 7:15"


async def _scheduled(served: Served, engine: AsyncEngine, **over: Any) -> Person:
    ada = await person(engine)
    await made_bot(served, ada, schedule={**WEEKDAYS, "every": "hour"}, **over)
    return ada


async def test_a_due_bot_runs_once_however_many_ticks_were_missed(served: Served, engine: AsyncEngine) -> None:
    ada = await _scheduled(served, engine)
    await _due(engine, ada, timedelta(hours=5))  # the server was down five hours
    assert await due.fire(served.app.state.bots) == 1
    assert await due.fire(served.app.state.bots) == 0  # its next run is in the next hour, not five behind
    await served.settled()
    (run,) = await _runs(engine, ada)
    assert (run.input, run.user_id, run.status) == ("is:unread", ada.user_id, "done")
    assert [t.message for t in served.agent.turns] == ["is:unread"]  # its schedule's input is what it is given
    async with engine.connect() as conn:
        mine = (Bot.org_id == ada.org_id, Bot.slug == "inbox-cat")
        then = (await conn.execute(select(Bot.next_run_at).where(*mine))).scalar_one()
    assert datetime.now(UTC) < then <= datetime.now(UTC) + timedelta(hours=1)


async def test_a_schedule_with_no_input_gives_the_run_the_bots_standing_task(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    await made_bot(served, ada, schedule={"every": "hour"})
    await _due(engine, ada, timedelta(minutes=1))
    assert await due.fire(served.app.state.bots, datetime.now(UTC)) == 1
    await served.settled()
    (run,) = await _runs(engine, ada)
    assert (run.input, run.status) == ("", "done")
    assert [t.message for t in served.agent.turns] == ["Answer the mail worth answering."]


async def test_a_due_bot_whose_run_is_still_live_is_skipped(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    asks = await connected(served, ada, allow=False)
    await made_bot(
        served,
        ada,
        schedule={**WEEKDAYS, "every": "hour"},
        connections=[{"connection_id": asks["id"], "tools": ["gmail-send-email"]}],
    )
    served.agent.script = [play((SEND, {"to": ["grace@navy.test"], "subject": "Re: Lunch"}))]
    await _due(engine, ada, timedelta(minutes=1))
    assert await due.fire(served.app.state.bots) == 1
    await served.settled()  # its run waits on the person's yes
    assert [r.status for r in await _runs(engine, ada)] == ["needs_input"]
    await _due(engine, ada, timedelta(minutes=1))
    with logged() as said:
        assert await due.fire(served.app.state.bots) == 0
    assert len(await _runs(engine, ada)) == 1
    assert any("skipped: The bot has a run going" in line.getMessage() for line in said), said


async def test_the_minute_tick_fires_the_due_bots(served: Served, engine: AsyncEngine, redis: Redis) -> None:
    ada = await _scheduled(served, engine)
    assert await tend.tend(engine, Hub(redis), BOTS, 60, None, bots=served.app.state.bots)
    assert await _runs(engine, ada) == []  # not due yet
    await _due(engine, ada, timedelta(seconds=1))
    assert await tend.tend(engine, Hub(redis), BOTS, 60, None, bots=served.app.state.bots)
    await served.settled()
    assert len(await _runs(engine, ada)) == 1
