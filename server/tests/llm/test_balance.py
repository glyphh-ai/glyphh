"""The overage balance in dollars: topped up through Stripe Checkout and credited once on the paid webhook, granted by
staff, its ledger, the connector's words for it, each org's rows its own, and nothing of it while hosted models are
off."""

import uuid
from datetime import date

import httpx
import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import seed, tenancy
from glyphh_server.llm import ledger
from glyphh_server.models import LlmBalance, LlmLedger, LlmUsageDay, Org, Plan, PlanVersion
from glyphh_server.ops.plans import newest_version
from tests.ada.mcp import data, refused, rpc, signed_in, text, tool
from tests.admin.conftest import platform_headers
from tests.db.helpers import member, person
from tests.fakes import FakeStripe
from tests.llm.conftest import API, ASK, billing, holding, org_with_key, paid_session, webhook


async def test_the_admin_tops_up_through_checkout_credited_once_when_paid(
    engine: AsyncEngine, hosted: httpx.AsyncClient, stripe: FakeStripe
) -> None:
    who = await person(engine)
    made = await hosted.post(f"{API}/v1/billing/topup", json={"amount_cents": 2_500}, headers=who.headers)
    assert made.status_code == 200 and made.json() == {"url": "https://checkout.stripe.test/cs_1"}
    (_, path, _), (_, _, session) = stripe.calls
    assert path == "/customers" and session["mode"] == "payment" and session["metadata[kind]"] == "llm_topup"
    assert session["line_items[0][price_data][unit_amount]"] == "2500"
    assert session["line_items[0][price_data][currency]"] == "usd"
    assert session["success_url"] == "http://localhost:3000/settings/billing?topup=1"
    assert session["cancel_url"] == "http://localhost:3000/settings/billing"
    await hosted.post(f"{API}/v1/billing/topup", json={"amount_cents": 1_000}, headers=who.headers)
    assert [c[1] for c in stripe.calls].count("/customers") == 1  # its customer made once
    for cents in (999, 100_001):
        res = await hosted.post(f"{API}/v1/billing/topup", json={"amount_cents": cents}, headers=who.headers)
        assert res.status_code == 422
    bob = await member(engine, who.org_id)
    res = await hosted.post(f"{API}/v1/billing/topup", json={"amount_cents": 1_000}, headers=bob.headers)
    assert res.status_code == 403
    unpaid = paid_session(who.org_id, 2_500, "cs_unpaid", status="unpaid")
    assert (await webhook(hosted, "checkout.session.completed", unpaid)).status_code == 204
    assert (await billing(hosted, who))["balance"]["micros"] == 0
    for _ in range(2):  # sent again: credited once
        await webhook(hosted, "checkout.session.async_payment_succeeded", paid_session(who.org_id, 2_500, "cs_paid"))
    nobody = paid_session(uuid.uuid4(), 9_900, "cs_nobody")
    assert (await webhook(hosted, "checkout.session.completed", nobody)).status_code == 204
    assert (await billing(hosted, who))["balance"] == {"cents": 2_500.0, "micros": 25_000_000, "low": False}
    entries = (await hosted.get(f"{API}/v1/billing/ledger?limit=1", headers=bob.headers)).json()["entries"]
    assert [(e["kind"], e["amount_cents"], e["model"], e["note"]) for e in entries] == [
        ("topup", 2_500.0, None, "cs_paid")
    ]


async def test_staff_grant_a_balance_shown_on_the_org(engine: AsyncEngine, hosted: httpx.AsyncClient) -> None:
    from glyphh_server.app import create_app
    from tests.conftest import _client
    from tests.fakes import fake_http
    from tests.llm.conftest import HOSTED

    email = f"staff-{uuid.uuid4().hex[:10]}@glyphh.test"
    settings = HOSTED.model_copy(
        update={"staff_emails": email, "platform_client_id": "0f0f0f0f-0000-4000-8000-00000000a0a0"}
    )
    staff, who = await person(engine, email=email), await person(engine)
    async for admin in _client(create_app(settings, http=fake_http())):
        headers = await platform_headers(engine, staff)
        grant = {"amount_cents": 500, "note": "  A welcome credit  "}
        res = await admin.post(f"/v1/admin/orgs/{who.org_id}/llm-grant", json=grant, headers=headers)
        assert res.status_code == 200 and res.json() == {"message": "Granted $5.00 to its overage balance."}
        missing = await admin.post(f"/v1/admin/orgs/{uuid.uuid4()}/llm-grant", json=grant, headers=headers)
        assert missing.status_code == 404
        shown = (await admin.get(f"/v1/admin/orgs/{who.org_id}", headers=headers)).json()
        assert shown["balance"] == {"cents": 500.0, "micros": 5_000_000, "low": False}
        granted = next(a for a in shown["audit"] if a["action"] == "adminGrantBalance")
        assert granted["detail"]["amount_cents"] == 500
    entries = (await hosted.get(f"{API}/v1/billing/ledger", headers=who.headers)).json()["entries"]
    assert [(e["kind"], e["amount_micros"], e["note"]) for e in entries] == [("grant", 5_000_000, "A welcome credit")]


async def test_the_connector_says_the_tokens_and_balance_and_tops_up(
    engine: AsyncEngine, hosted: httpx.AsyncClient
) -> None:
    who, key = await org_with_key(engine, hosted)
    await holding(engine, who.org_id, micros=-12_345, tokens=260_000)
    auth = await signed_in(engine, who)
    used = text(await tool(hosted, auth, "usage"))
    assert "Hosted-model tokens" in used and "250,000 of 250,000, 10,000 past it" in used
    assert "Overage balance: -$0.01 (low: add funds with topup)." in used
    plan = await tool(hosted, auth, "plan")
    assert "Overage balance: -$0.01" in text(plan) and data(plan)["balance"]["micros"] == -12_345
    plans = await tool(hosted, auth, "plans")
    assert "hosted-model tokens a month 250,000" in text(plans) and "hosted-model tokens a month by contract" in text(
        plans
    )
    assert "$0.60 per million input tokens, $2.40 per million output tokens" in text(plans)
    assert data(plans)["models"][0]["id"] == "adal-34b-1-0"
    topped = await tool(hosted, auth, "topup", amount_cents=5_000)
    assert "add $50.00 to your overage balance" in text(topped) and data(topped)["url"].startswith("https://")
    assert (await refused(hosted, auth, "topup", amount_cents=5))["code"] == "E_INVALID"
    enterprise = await person(engine, "Enterprise")
    assert "of by contract" in text(await tool(hosted, await signed_in(engine, enterprise), "usage"))
    assert (await hosted.post("/v1/chat/completions", json=ASK, headers=key)).status_code == 402


async def test_hosted_models_off_show_nothing_of_them(
    engine: AsyncEngine, client: httpx.AsyncClient, ada: httpx.AsyncClient
) -> None:
    who = await person(engine)
    shown = (await client.get("/v1/billing", headers=who.headers)).json()
    # the bots' tokens are metered whether hosted models are on or not, so the month and the balance still show
    assert (shown["tokens"]["models"], shown["tokens"]["max"], shown["balance"]["micros"]) == ([], 250_000, 0)
    assert (await ada.post("/v1/chat/completions", json=ASK, headers=who.headers)).status_code == 404
    names = [t["name"] for t in (await rpc(ada, await signed_in(engine, who), "tools/list"))["result"]["tools"]]
    assert "topup" not in names and "usage" in names


async def test_each_orgs_tokens_and_money_are_its_own(engine: AsyncEngine) -> None:
    ada, eve = await person(engine), await person(engine)
    async with engine.begin() as conn:
        for who in (ada, eve):
            await ledger.credit(conn, who.org_id, "grant", 1_000)
            await ledger.charge(conn, who.org_id, "adal-34b-1-0", "2026-11-10", 10)
            day = {"org_id": who.org_id, "model": "adal-34b-1-0", "day": date(2026, 11, 10)}
            await conn.execute(insert(LlmUsageDay).values(**day))
    async with engine.begin() as conn:
        await tenancy.enter(conn, ada.org_id)
        for table in (LlmLedger, LlmBalance, LlmUsageDay):
            assert set((await conn.execute(select(table.org_id))).scalars()) == {ada.org_id}
        gone = await conn.execute(update(LlmBalance).where(LlmBalance.org_id == eve.org_id).values(micros=10**9))
        assert gone.rowcount == 0
    with pytest.raises(DBAPIError, match="row-level security"):
        async with engine.begin() as conn:
            await tenancy.enter(conn, ada.org_id)
            await ledger.credit(conn, eve.org_id, "grant", 10**9)


async def test_a_new_allowance_alone_is_a_new_version_that_takes_the_price_and_the_orgs(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        plan_id = (await conn.execute(insert(Plan).values(name="Carry tokens", sort=9).returning(Plan.id))).scalar_one()
        values = {"plan_id": plan_id, "version": 1, "price_cents": 4_900, "billing_interval": "month"}
        made = insert(PlanVersion).values(**values, stripe_price_id="price_test_tokens", max_machines=2)
        old = (await conn.execute(made.returning(PlanVersion.id))).scalar_one()
    who = await person(engine)
    async with engine.begin() as conn:
        await conn.execute(update(Org).where(Org.id == who.org_id).values(plan_version_id=old))
        carry = seed.PlanSeed("Carry tokens", 4_900, "month", True, 2, None, seed.Features(), llm_tokens=7_000)
        await seed._seed_version(conn, carry, None)
        new = await newest_version(conn, "Carry tokens")
        assert (new.version, new.llm_tokens, new.stripe_price_id, new.max_machines) == (
            2,
            7_000,
            "price_test_tokens",
            2,
        )
        pinned = (await conn.execute(select(Org.plan_version_id).where(Org.id == who.org_id))).scalar_one()
        assert pinned == new.id
        await conn.execute(update(Plan).where(Plan.id == plan_id).values(active=False))
        count = select(func.count()).where(PlanVersion.plan_id == plan_id)
        assert (await conn.execute(count)).scalar_one() == 2
