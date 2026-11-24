"""The org's use day by day for the Usage charts: Ada reads, the decides among them, and the balance's charges."""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import AdaModelDay, LlmUsageDay
from tests.db.helpers import person


async def test_each_day_of_the_window_oldest_first(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    who, other = await person(engine), await person(engine)
    today = datetime.now(UTC).date()
    yesterday = today - timedelta(days=1)
    async with engine.begin() as conn:
        for metric, day, n in (("read:decide", today, 5), ("read:query", today, 2), ("decided", today, 9)):
            await conn.execute(insert(AdaModelDay).values(org_id=who.org_id, model="m", day=day, metric=metric, n=n))
        await conn.execute(
            insert(AdaModelDay).values(org_id=who.org_id, model="m", day=yesterday, metric="read:beam", n=1)
        )
        usage = {"org_id": who.org_id, "day": yesterday, "input_tokens": 1, "output_tokens": 1, "requests": 1}
        await conn.execute(insert(LlmUsageDay).values(**usage, model="adal-34b-1-0", charged_micros=25_000))
        await conn.execute(
            insert(AdaModelDay).values(org_id=other.org_id, model="m", day=today, metric="read:decide", n=99)
        )
    days = (await client.get("/v1/billing/series?days=7", headers=who.headers)).json()["days"]
    assert len(days) == 7 and days[-1]["day"] == today.isoformat()
    assert days[-1] == {
        "day": today.isoformat(),
        "reads": 7,
        "decides": 5,
        "charged_cents": 0.0,
        "charged_micros": 0,
    }
    assert (days[-2]["reads"], days[-2]["decides"], days[-2]["charged_cents"]) == (1, 0, 2.5)
    assert days[0] == {"day": days[0]["day"], "reads": 0, "decides": 0, "charged_cents": 0.0, "charged_micros": 0}
    assert len((await client.get("/v1/billing/series", headers=who.headers)).json()["days"]) == 30
    assert (await client.get("/v1/billing/series?days=91", headers=who.headers)).status_code == 422
