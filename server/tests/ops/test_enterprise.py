"""Enterprise, granted by staff: the org on Enterprise until a date at its own markup, billed on its own subscription;
revoked back to Free, its machines stopped and held; ended by the tick when the date passes, and when the deal's
subscription ends; revoked or ended, its hosting due reported to the deal's subscription first; the command refuses
what it cannot do."""

import runpy
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import MachineMonth, Org, Rrotor
from glyphh_server.ops import enterprise
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.billing.sync import sync_subscription
from glyphh_server.ops.plans import org_version
from tests.conftest import SETTINGS
from tests.db.helpers import org_row, person, subscribed
from tests.fakes import FakeStripe, fake_http
from tests.link import hosted_runtime


async def _plan(engine: AsyncEngine, org_id: uuid.UUID) -> str:
    async with engine.connect() as conn:
        return (await org_version(conn, org_id)).name


async def test_a_grant_puts_the_org_on_enterprise_at_its_markup_on_its_subscription(
    engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Pro")
    sub, customer = f"sub_deal_{ada.org_id.hex}", f"cus_deal_{ada.org_id.hex}"
    stripe.sub(sub, customer, "price_deal_acme", 1)
    argv = ["grant", "--org", str(ada.org_id), "--until", "2027-10-31", "--markup", "15", "--subscription", sub]
    said = await enterprise.run(argv, SETTINGS, fake_http(stripe))
    assert said == f"Ada Lovelace's org is on Enterprise through 2027-10-31, at 15%, billed on {sub} ({customer})."
    org = await org_row(engine, ada.org_id)
    assert (org.plan_until, org.markup_pct, org.stripe_subscription_id, org.stripe_customer_id, org.billing_status) == (
        datetime(2027, 11, 1, tzinfo=UTC),
        15,
        sub,
        customer,
        "active",
    )
    assert await _plan(engine, ada.org_id) == "Enterprise"
    stripe.sub(sub, customer, "price_deal_acme", 1, "trialing_forever")
    await enterprise.run(argv, SETTINGS, fake_http(stripe))  # again, the same deal: its status taken as it is
    assert (await org_row(engine, ada.org_id)).billing_status == "none"
    async with engine.begin() as conn:
        await sync_subscription(conn, ada.org_id, stripe.subs[sub])  # its custom price is no plan's
    assert await _plan(engine, ada.org_id) == "Enterprise"
    renewed = f"sub_renewed_{ada.org_id.hex}"
    stripe.sub(renewed, customer, "price_deal_acme_2", 1)
    argv = ["grant", "--org", str(ada.org_id), "--until", "2028-10-31", "--markup", "12", "--subscription", renewed]
    await enterprise.run(argv, SETTINGS, fake_http(stripe))  # renewed on a new subscription: no need to cancel first
    org = await org_row(engine, ada.org_id)
    assert (org.stripe_subscription_id, org.markup_pct, org.plan_until.year) == (renewed, 12, 2028)
    sub = renewed
    stripe.subs[sub]["status"] = "canceled"
    async with engine.begin() as conn:
        await sync_subscription(conn, ada.org_id, stripe.subs[sub])  # the deal's subscription ended
    org = await org_row(engine, ada.org_id)
    assert (await _plan(engine, ada.org_id), org.plan_until, org.markup_pct) == ("Free", None, None)


async def test_a_grant_refuses_another_subscription_and_an_unknown_org(engine: AsyncEngine, stripe: FakeStripe) -> None:
    ada = await person(engine, "Pro")
    await subscribed(engine, ada.org_id, "sub_pro", "cus_pro")
    stripe.sub("sub_deal2", "cus_pro", "price_deal", 1)
    with pytest.raises(Conflict, match="Cancel the org's subscription sub_pro first"):
        await enterprise.grant(engine, _stripe(stripe), ada.org_id, date(2027, 1, 1), 20, "sub_deal2")
    with pytest.raises(NotFound):
        await enterprise.grant(engine, _stripe(stripe), uuid.uuid4(), date(2027, 1, 1), 20, "sub_deal2")
    with pytest.raises(SystemExit):
        argv = ["grant", "--org", str(ada.org_id), "--until", "2027-01-01", "--markup", "-5", "--subscription", "x"]
        await enterprise.run(argv, SETTINGS, fake_http(stripe))
    with pytest.raises(SystemExit):
        await enterprise.run(["grant", "--org", "not-a-uuid"], SETTINGS, fake_http(stripe))


def _stripe(stripe: FakeStripe, meter: str = "") -> StripeClient:
    return StripeClient(fake_http(stripe), "sk_test", meter)


async def _a_deal_with_hosting_due(engine: AsyncEngine, who: Any, cents: int) -> str:
    """The org's deal on its own subscription, its machines having charged this many cents not yet reported."""
    customer = f"cus_deal_{who.org_id.hex}"
    await subscribed(engine, who.org_id, f"sub_deal_{who.org_id.hex}", customer)
    async with engine.begin() as conn:
        values = {"rrotor_id": uuid.uuid4(), "month": "2026-10", "org_id": who.org_id, "name": "m", "size": "small"}
        await conn.execute(insert(MachineMonth).values(**values, cost_micros=0, charge_micros=cents * 10_000))
    return customer


def _reported(stripe: FakeStripe, customer: str) -> list[str]:
    return [
        b["payload[value]"]
        for _, p, b in stripe.calls
        if p == "/billing/meter_events" and b["payload[stripe_customer_id]"] == customer
    ]


async def test_revoking_puts_the_org_on_free_its_machines_stopped_and_held_its_hosting_reported(
    engine: AsyncEngine, stripe: FakeStripe
) -> None:
    from tests.api.test_hosted import FLY_SETTINGS
    from tests.fakes import FakeFly

    ada = await person(engine, "Enterprise")
    async with engine.begin() as conn:
        values = {"markup_pct": 10, "plan_until": datetime(2030, 1, 1, tzinfo=UTC)}
        await conn.execute(update(Org).where(Org.id == ada.org_id).values(**values))
    customer = await _a_deal_with_hosting_due(engine, ada, 250)
    kept = await hosted_runtime(engine, ada, f"k_{ada.org_id.hex[:8]}")  # the oldest: Free's one runs on
    machine = await hosted_runtime(engine, ada, f"m_{ada.org_id.hex[:8]}")
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == kept.id).values(state="online", fly_machine_id="m_k"))
        await conn.execute(update(Rrotor).where(Rrotor.id == machine.id).values(state="online", fly_machine_id="m_x"))
    fly = FakeFly()
    fly.machines["m_x"] = {"id": "m_x", "state": "started"}
    fly.machines["m_k"] = {"id": "m_k", "state": "started"}
    said = await enterprise.run(
        ["revoke", "--org", str(ada.org_id)],
        FLY_SETTINGS.model_copy(update={"database_url": SETTINGS.database_url}),
        fake_http(stripe, fly=fly),
    )
    assert said == "Ada Lovelace's org is on Free, 1 hosted machines stopped. Cancel its subscription in Stripe."
    assert _reported(stripe, customer) == ["250"]  # to the deal's subscription, before it was dropped
    assert (fly.machines["m_x"]["state"], fly.machines["m_k"]["state"]) == ("stopped", "started")
    org = await org_row(engine, ada.org_id)
    assert (await _plan(engine, ada.org_id), org.plan_until, org.markup_pct) == ("Free", None, None)
    unbilled = SETTINGS.model_copy(update={"stripe_secret_key": ""})
    said = await enterprise.run(["revoke", "--org", str(ada.org_id)], unbilled)  # hosting and billing off
    assert said == "Ada Lovelace's org is on Free, 0 hosted machines stopped. Cancel its subscription in Stripe."


async def test_a_grant_past_its_date_ends_at_the_tick_its_hosting_reported_first(
    engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ended, kept, left = [await person(engine, "Enterprise") for _ in range(3)]
    customer = await _a_deal_with_hosting_due(engine, ended, 75)
    async with engine.begin() as conn:
        for who, until in ((ended, -1), (kept, 30), (left, -1)):
            values = {"plan_until": datetime.now(UTC) + timedelta(days=until), "markup_pct": 20}
            await conn.execute(update(Org).where(Org.id == who.org_id).values(**values))
    await hosted_runtime(engine, left)
    assert set(await enterprise.expire(engine, _stripe(stripe, "glyphh_hosting"))) >= {ended.org_id, left.org_id}
    assert [await _plan(engine, w.org_id) for w in (ended, kept, left)] == ["Free", "Enterprise", "Free"]
    assert _reported(stripe, customer) == ["75"]  # to the deal's subscription, before it was dropped
    assert (await org_row(engine, ended.org_id)).stripe_subscription_id is None


def test_the_command_runs_as_a_module_and_says_what_it_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    import warnings

    monkeypatch.setattr(sys, "argv", ["enterprise", "revoke", "--org", str(uuid.uuid4())])
    with warnings.catch_warnings(), pytest.raises(SystemExit, match=r"Refused: There is no such org\."):
        warnings.simplefilter("ignore", RuntimeWarning)
        runpy.run_module("glyphh_server.ops.enterprise", run_name="__main__")
