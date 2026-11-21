"""The org's usage on /v1/billing beyond the plan's precedents: its connections against the plan's and their price,
each model's month of tokens (the bots' Claude models beside the hosted ones), each bot's month, and the balance's
top-up open whether hosted models are on or not."""

from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.llm import ledger
from glyphh_server.models import Bot, BotRun, Connection, LlmUsageDay, Org, Plan, PlanVersion
from glyphh_server.ops.bot_usage import month_start
from tests.db.helpers import person
from tests.fakes import FakeStripe


async def _priced(engine: AsyncEngine, org_id: object, included: int | None, cents: int | None) -> None:
    """The org on a plan of its own with these connections included and this price past them."""
    async with engine.begin() as conn:
        made = insert(Plan).values(name=f"Conn {org_id}", sort=20, active=False)  # never listed: the org's alone
        plan = await conn.execute(made.returning(Plan.id))
        values = {"plan_id": plan.scalar_one(), "version": 1, "price_cents": 1_000, "billing_interval": "month"}
        made = insert(PlanVersion).values(**values, connections=included, connection_cents=cents, llm_tokens=10)
        version = (await conn.execute(made.returning(PlanVersion.id))).scalar_one()
        await conn.execute(update(Org).where(Org.id == org_id).values(plan_version_id=version))


async def _connections(engine: AsyncEngine, org_id: object, n: int) -> None:
    async with engine.begin() as conn:
        for i in range(n):
            row = {"org_id": org_id, "app": "gmail", "app_name": "Gmail", "account_id": f"apn_{org_id}_{i}"}
            await conn.execute(insert(Connection).values(**row))


async def test_connections_are_counted_against_the_plans_and_priced_past_them(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    free = await person(engine)
    await _connections(engine, free.org_id, 2)
    shown = (await client.get("/v1/billing", headers=free.headers)).json()["connections"]
    assert shown == {"used": 2, "included": None, "over": 0, "cents_a_month": None, "due_cents": None}

    priced = await person(engine)
    await _priced(engine, priced.org_id, 1, 500)
    await _connections(engine, priced.org_id, 3)
    billing = (await client.get("/v1/billing", headers=priced.headers)).json()
    assert billing["plan"]["connections"] == {"included": 1, "cents_a_month": 500}
    assert billing["connections"] == {"used": 3, "included": 1, "over": 2, "cents_a_month": 500, "due_cents": 1_000}

    capped = await person(engine)
    await _priced(engine, capped.org_id, 5, None)  # a cap set, no price yet
    await _connections(engine, capped.org_id, 1)
    held = (await client.get("/v1/billing", headers=capped.headers)).json()["connections"]
    assert held == {"used": 1, "included": 5, "over": 0, "cents_a_month": None, "due_cents": None}


async def test_the_bots_tokens_show_by_model_and_by_bot(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    who = await person(engine)
    today = datetime.now(UTC)
    async with engine.begin() as conn:
        for model, charged in (("claude-sonnet-5-5", 25_000), ("adal-34b-1-0", 0), ("retired-model", 0)):
            day = {"org_id": who.org_id, "day": today.date(), "model": model, "input_tokens": 1_000}
            await conn.execute(insert(LlmUsageDay).values(**day, output_tokens=200, requests=3, charged_micros=charged))
        bots = {}
        for slug, name in (("inbox", "Inbox triage"), ("notes", "Standup notes"), ("idle", "Idle")):
            made = insert(Bot).values(org_id=who.org_id, slug=slug, name=name, model="claude-sonnet-5-5")
            bots[slug] = (await conn.execute(made.returning(Bot.id))).scalar_one()
        last_month = month_start(ledger.period()) - timedelta(days=1)  # not this month's: not counted
        runs = [("inbox", 100, 20, 30_000, today), ("inbox", 50, 10, 0, today), ("notes", 10, 5, 0, today)]
        runs.append(("idle", 999, 999, 999, last_month))
        for slug, i, o, cost, at in runs:
            row = {"org_id": who.org_id, "bot_id": bots[slug], "input_tokens": i, "output_tokens": o}
            await conn.execute(insert(BotRun).values(**row, cost_micros=cost, status="done", created_at=at))
    billing = (await client.get("/v1/billing", headers=who.headers)).json()
    models = {m["id"]: (m["name"], m["kind"], m["charged_cents"]) for m in billing["tokens"]["models"]}
    assert models == {
        "claude-sonnet-5-5": ("Claude Sonnet 5.5", "bot", 2.5),
        "adal-34b-1-0": ("adaL 34B 1.0", "hosted", 0.0),
        "retired-model": ("retired-model", "hosted", 0.0),
    }
    assert billing["bots"] == [
        {
            "slug": "inbox",
            "name": "Inbox triage",
            "runs": 2,
            "input_tokens": 150,
            "output_tokens": 30,
            "charged_cents": 3.0,
            "charged_micros": 30_000,
        },
        {
            "slug": "notes",
            "name": "Standup notes",
            "runs": 1,
            "input_tokens": 10,
            "output_tokens": 5,
            "charged_cents": 0.0,
            "charged_micros": 0,
        },
    ]


async def test_the_admin_tops_up_with_hosted_models_off(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    who = await person(engine)
    res = await client.post("/v1/billing/topup", json={"amount_cents": 2_500}, headers=who.headers)
    assert res.status_code == 200 and res.json()["url"].startswith("https://")
    session = stripe.calls[-1][2]
    assert session["line_items[0][price_data][product_data][name]"] == "Glyphh balance (bots and hosted models)"
