"""The org's usage on /v1/billing beyond the plan: each hosted model's month of tokens, and the balance's top-up open
whether hosted models are on or not."""

from datetime import UTC, datetime

import httpx
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import LlmUsageDay
from tests.db.helpers import person
from tests.fakes import FakeStripe


async def test_the_months_tokens_show_by_model(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    who = await person(engine)
    today = datetime.now(UTC)
    async with engine.begin() as conn:
        for model, charged in (("adal-34b-1-0", 25_000), ("retired-model", 0)):
            day = {"org_id": who.org_id, "day": today.date(), "model": model, "input_tokens": 1_000}
            await conn.execute(insert(LlmUsageDay).values(**day, output_tokens=200, requests=3, charged_micros=charged))
    billing = (await client.get("/v1/billing", headers=who.headers)).json()
    models = {m["id"]: (m["name"], m["kind"], m["charged_cents"]) for m in billing["tokens"]["models"]}
    assert models == {
        "adal-34b-1-0": ("adaL 34B 1.0", "hosted", 2.5),
        "retired-model": ("retired-model", "hosted", 0.0),
    }
    assert "bots" not in billing and "connections" not in billing


async def test_the_admin_tops_up_with_hosted_models_off(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    who = await person(engine)
    res = await client.post("/v1/billing/topup", json={"amount_cents": 2_500}, headers=who.headers)
    assert res.status_code == 200 and res.json()["url"].startswith("https://")
    session = stripe.calls[-1][2]
    assert session["line_items[0][price_data][product_data][name]"] == "Glyphh balance (hosted models)"
