"""Enterprise, granted by staff: the org on Enterprise until a date, billed on its own subscription, with a licence key
to then; revoked back to Free, its keys revoked; ended by the tick when the date passes, and when the deal's
subscription ends; the command refuses what it cannot do."""

import runpy
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.db import tenancy
from glyphh_server.errors import Conflict, NotFound
from glyphh_server.models import Org
from glyphh_server.ops import enterprise, license_keys
from glyphh_server.ops.billing.stripe import StripeClient
from glyphh_server.ops.billing.sync import sync_subscription
from glyphh_server.ops.plans import org_version
from tests.conftest import SETTINGS
from tests.db.helpers import org_row, person, subscribed
from tests.fakes import FakeStripe, fake_http

KEY: Ed25519PrivateKey = Ed25519PrivateKey.generate()


async def _plan(engine: AsyncEngine, org_id: uuid.UUID) -> str:
    async with engine.connect() as conn:
        return (await org_version(conn, org_id)).name


async def _key(engine: AsyncEngine, org_id: uuid.UUID) -> str | None:
    async with engine.begin() as conn:
        await tenancy.enter(conn, org_id)
        return await license_keys.newest(conn, org_id)


async def test_a_grant_puts_the_org_on_enterprise_on_its_subscription(engine: AsyncEngine, stripe: FakeStripe) -> None:
    ada = await person(engine, "Pro")
    sub, customer = f"sub_deal_{ada.org_id.hex}", f"cus_deal_{ada.org_id.hex}"
    stripe.sub(sub, customer, "price_deal_acme", 1)
    argv = ["grant", "--org", str(ada.org_id), "--until", "2027-10-31", "--subscription", sub]
    said = await enterprise.run(argv, SETTINGS, fake_http(stripe))
    assert said == f"Ada Lovelace's org is on Enterprise through 2027-10-31, billed on {sub} ({customer})."
    org = await org_row(engine, ada.org_id)
    assert (org.plan_until, org.stripe_subscription_id, org.stripe_customer_id, org.billing_status) == (
        datetime(2027, 11, 1, tzinfo=UTC),
        sub,
        customer,
        "active",
    )
    assert await _plan(engine, ada.org_id) == "Enterprise" and await _key(engine, ada.org_id) is not None
    stripe.sub(sub, customer, "price_deal_acme", 1, "trialing_forever")
    await enterprise.run(argv, SETTINGS, fake_http(stripe))  # again, the same deal: its status taken as it is
    assert (await org_row(engine, ada.org_id)).billing_status == "none"
    async with engine.begin() as conn:
        await sync_subscription(conn, ada.org_id, stripe.subs[sub])  # its custom price is no plan's
    assert await _plan(engine, ada.org_id) == "Enterprise"
    renewed = f"sub_renewed_{ada.org_id.hex}"
    stripe.sub(renewed, customer, "price_deal_acme_2", 1)
    argv = ["grant", "--org", str(ada.org_id), "--until", "2028-10-31", "--subscription", renewed]
    await enterprise.run(argv, SETTINGS, fake_http(stripe))  # renewed on a new subscription: no need to cancel first
    org = await org_row(engine, ada.org_id)
    assert (org.stripe_subscription_id, org.plan_until.year) == (renewed, 2028)
    stripe.subs[renewed]["status"] = "canceled"
    async with engine.begin() as conn:
        await sync_subscription(conn, ada.org_id, stripe.subs[renewed])  # the deal's subscription ended
    org = await org_row(engine, ada.org_id)
    assert (await _plan(engine, ada.org_id), org.plan_until) == ("Free", None)


async def test_a_grant_refuses_another_subscription_and_an_unknown_org(engine: AsyncEngine, stripe: FakeStripe) -> None:
    ada = await person(engine, "Pro")
    await subscribed(engine, ada.org_id, "sub_pro", "cus_pro")
    stripe.sub("sub_deal2", "cus_pro", "price_deal", 1)
    billing = StripeClient(fake_http(stripe), "sk_test")
    with pytest.raises(Conflict, match="Cancel the org's subscription sub_pro first"):
        await enterprise.grant(engine, billing, ada.org_id, date(2027, 1, 1), "sub_deal2", KEY)
    with pytest.raises(NotFound):
        await enterprise.grant(engine, billing, uuid.uuid4(), date(2027, 1, 1), "sub_deal2", KEY)
    with pytest.raises(SystemExit):
        argv = ["grant", "--org", str(ada.org_id), "--until", "2027-01-01", "--markup", "5", "--subscription", "x"]
        await enterprise.run(argv, SETTINGS, fake_http(stripe))
    with pytest.raises(SystemExit):
        await enterprise.run(["grant", "--org", "not-a-uuid"], SETTINGS, fake_http(stripe))


async def test_revoking_puts_the_org_on_free_and_revokes_its_keys(engine: AsyncEngine, stripe: FakeStripe) -> None:
    ada = await person(engine, "Pro")
    sub, customer = f"sub_deal_{ada.org_id.hex}", f"cus_deal_{ada.org_id.hex}"
    stripe.sub(sub, customer, "price_deal_acme", 1)
    argv = ["grant", "--org", str(ada.org_id), "--until", "2030-01-01", "--subscription", sub]
    await enterprise.run(argv, SETTINGS, fake_http(stripe))
    assert await _key(engine, ada.org_id) is not None
    said = await enterprise.run(["revoke", "--org", str(ada.org_id)], SETTINGS, fake_http(stripe))
    assert said == "Ada Lovelace's org is on Free. Cancel its subscription in Stripe."
    org = await org_row(engine, ada.org_id)
    assert (await _plan(engine, ada.org_id), org.plan_until, org.stripe_subscription_id) == ("Free", None, None)
    assert await _key(engine, ada.org_id) is None


async def test_a_grant_past_its_date_ends_at_the_tick(engine: AsyncEngine) -> None:
    ended, kept = await person(engine, "Enterprise"), await person(engine, "Enterprise")
    await subscribed(engine, ended.org_id, f"sub_deal_{ended.org_id.hex}", f"cus_deal_{ended.org_id.hex}")
    async with engine.begin() as conn:
        for who, until in ((ended, -1), (kept, 30)):
            values = {"plan_until": datetime.now(UTC) + timedelta(days=until)}
            await conn.execute(update(Org).where(Org.id == who.org_id).values(**values))
    assert ended.org_id in await enterprise.expire(engine)
    assert [await _plan(engine, w.org_id) for w in (ended, kept)] == ["Free", "Enterprise"]
    assert (await org_row(engine, ended.org_id)).stripe_subscription_id is None


def test_the_command_runs_as_a_module_and_says_what_it_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    import warnings

    monkeypatch.setattr(sys, "argv", ["enterprise", "revoke", "--org", str(uuid.uuid4())])
    with warnings.catch_warnings(), pytest.raises(SystemExit, match=r"Refused: There is no such org\."):
        warnings.simplefilter("ignore", RuntimeWarning)
        runpy.run_module("glyphh_server.ops.enterprise", run_name="__main__")
