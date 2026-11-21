"""The org's use day by day for the Usage charts: Ada reads, bot runs, charges and the connections held."""

from datetime import UTC, datetime, time, timedelta

import httpx
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import AdaModelDay, Bot, BotRun, Connection, LlmUsageDay
from tests.db.helpers import person


async def test_each_day_of_the_window_oldest_first(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    who, other = await person(engine), await person(engine)
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    at = lambda day: datetime.combine(day, time(12), UTC)  # noqa: E731
    async with engine.begin() as conn:
        for metric, day, n in (("read:decide", today, 5), ("read:query", today, 2), ("decided", today, 9)):
            await conn.execute(insert(AdaModelDay).values(org_id=who.org_id, model="m", day=day, metric=metric, n=n))
        await conn.execute(
            insert(AdaModelDay).values(org_id=who.org_id, model="m", day=yesterday, metric="read:beam", n=1)
        )
        made = insert(Bot).values(org_id=who.org_id, slug="inbox", name="Inbox", model="claude-sonnet-5-5")
        bot = (await conn.execute(made.returning(Bot.id))).scalar_one()
        for day in (today, today, yesterday, today - timedelta(days=40)):
            await conn.execute(insert(BotRun).values(org_id=who.org_id, bot_id=bot, status="done", created_at=at(day)))
        usage = {"org_id": who.org_id, "day": yesterday, "input_tokens": 1, "output_tokens": 1, "requests": 1}
        await conn.execute(insert(LlmUsageDay).values(**usage, model="claude-sonnet-5-5", charged_micros=25_000))
        for i, day in enumerate((today - timedelta(days=10), yesterday, today)):
            row = {"org_id": who.org_id, "app": "gmail", "app_name": "Gmail", "account_id": f"apn_s_{who.org_id}_{i}"}
            await conn.execute(insert(Connection).values(**row, created_at=at(day)))
        await conn.execute(
            insert(AdaModelDay).values(org_id=other.org_id, model="m", day=today, metric="read:decide", n=99)
        )
    days = (await client.get("/v1/billing/series?days=7", headers=who.headers)).json()["days"]
    assert len(days) == 7 and days[-1]["day"] == today.isoformat() and days[0]["connections"] == 1
    assert days[-1] == {
        "day": today.isoformat(),
        "reads": 7,
        "decides": 5,
        "bot_runs": 2,
        "charged_cents": 0.0,
        "charged_micros": 0,
        "connections": 3,
        "connections_added": 1,
    }
    assert (days[-2]["reads"], days[-2]["decides"], days[-2]["bot_runs"]) == (1, 0, 1)
    assert (days[-2]["charged_cents"], days[-2]["connections"], days[-2]["connections_added"]) == (2.5, 2, 1)
    assert (await client.get("/v1/billing/series", headers=who.headers)).json()["days"][0]["connections"] == 0
    assert (await client.get("/v1/billing/series?days=91", headers=who.headers)).status_code == 422
