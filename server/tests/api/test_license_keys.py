"""The licence key (rrotor's docs/specs/licensing.md): its exact format, signed with the server's key; issued at each
payment to the paid period's end and at an Enterprise grant through its last day, never on Free; revoked when the
subscription or grant ends; listed for the platform and shown masked by the connector."""

import base64
import json
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops import enterprise, license_keys
from glyphh_server.ops.billing.signature import sign
from glyphh_server.ops.billing.stripe import StripeClient
from tests.conftest import WEBHOOK_SECRET
from tests.connector import granted, tool
from tests.db.helpers import member, person, subscribed
from tests.fakes import FakeStripe, fake_http

FIELDS = [
    "license_id",
    "tier",
    "max_nodes",
    "max_precedents",
    "cluster_sync_enabled",
    "issued_at",
    "expires_at",
    "customer_id",
]
PERIOD_END: int = 1_900_000_000


def unb64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def read(key: str, public: Ed25519PublicKey | None = None) -> dict[str, Any]:
    """As rrotor reads it: two base64url parts without padding, the signature over the payload's exact bytes."""
    assert "=" not in key and "+" not in key and "/" not in key
    payload, signature = key.split(".")
    raw = unb64(payload)
    if public is not None:
        public.verify(unb64(signature), raw)
    return json.loads(raw)


async def server_key(client: httpx.AsyncClient, headers: dict[str, str]) -> Ed25519PublicKey:
    said = (await client.get("/v1/license/key", headers=headers)).json()
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(said["public_key"]))


async def send(client: httpx.AsyncClient, kind: str, obj: dict[str, Any]) -> None:
    body = json.dumps({"id": "evt_k", "type": kind, "data": {"object": obj}}).encode()
    headers = {"stripe-signature": sign(WEBHOOK_SECRET, body, int(time.time())), "content-type": "application/json"}
    assert (await client.post("/v1/stripe/webhook", content=body, headers=headers)).status_code == 204


def paid_sub(
    stripe: FakeStripe, sub_id: str, customer: str, price: str, end: int | None, status: str = "active"
) -> None:
    item = stripe.sub(sub_id, customer, price, 1, status)["items"]["data"][0]
    if end is not None:
        item["current_period_end"] = end


async def listed(client: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    res = await client.get("/v1/license/keys", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


async def test_a_key_is_the_payload_and_its_signature_exactly_and_never_on_free(engine: AsyncEngine) -> None:
    signer, ada = Ed25519PrivateKey.generate(), await person(engine, "Pro")
    until = datetime(2027, 1, 31, 12, 30, 15, 999, tzinfo=UTC)
    async with engine.begin() as conn:
        key = await license_keys.issue(conn, signer, ada.org_id, until)
        assert key is not None and await license_keys.issue(conn, signer, ada.org_id, until) == key  # same terms
        assert await license_keys.issue(conn, signer, (await person(engine)).org_id, until) is None  # Free: none
        basic = (await person(engine, "Basic")).org_id  # Basic: none either (rrotor has no basic tier)
        assert await license_keys.issue(conn, signer, basic, until) is None
    payload = read(key, signer.public_key())
    assert list(payload) == FIELDS
    assert uuid.UUID(payload["license_id"]) and payload["customer_id"] == str(ada.org_id)
    assert (payload["tier"], payload["max_nodes"], payload["max_precedents"]) == ("pro", 3, 50_000)
    assert payload["cluster_sync_enabled"] is True and payload["expires_at"] == "2027-01-31T12:30:15Z"
    issued = datetime.strptime(payload["issued_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert abs(issued - datetime.now(UTC)) < timedelta(minutes=1)
    one_byte = key[:10] + ("A" if key[10] != "A" else "B") + key[11:]
    with pytest.raises(InvalidSignature):
        read(one_byte, signer.public_key())
    assert license_keys.masked(key) == f"{key[:8]}…{key[-6:]}" and license_keys.masked(None) is None


async def test_a_payment_issues_a_key_to_the_paid_periods_end_and_an_ended_subscription_revokes_it(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    bob = await member(engine, ada.org_id)
    sub, customer = f"sub_k_{ada.org_id.hex}", f"cus_k_{ada.org_id.hex}"
    paid_sub(stripe, sub, customer, "price_test_team", PERIOD_END)
    checkout = {"mode": "subscription", "client_reference_id": str(ada.org_id), "customer": customer}
    await send(client, "checkout.session.completed", checkout | {"subscription": sub})
    first = await listed(client, bob.headers)  # any member: their runtimes carry it
    payload = read(first["license_key"], await server_key(client, ada.headers))
    assert (payload["tier"], payload["max_nodes"], payload["max_precedents"]) == ("team", 10, 500_000)
    assert payload["expires_at"] == datetime.fromtimestamp(PERIOD_END, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    view = first["keys"][0]
    assert (view["state"], view["key"], view["revoked_at"], view["license_id"]) == (
        "live",
        first["license_key"],
        None,
        payload["license_id"],
    )
    old_style = {"customer": customer, "subscription": sub}
    await send(client, "invoice.payment_succeeded", old_style)  # the checkout's own invoice: the same key
    assert len((await listed(client, ada.headers))["keys"]) == 1
    stripe.subs[sub]["items"]["data"][0]["current_period_end"] = PERIOD_END + 2_592_000  # the next month, paid
    new_style = {"customer": customer, "parent": {"subscription_details": {"subscription": sub, "metadata": {}}}}
    await send(client, "invoice.payment_succeeded", new_style)
    second = await listed(client, ada.headers)
    assert len(second["keys"]) == 2 and second["license_key"] != first["license_key"]
    assert second["keys"][0]["key"] == second["license_key"] and second["keys"][0]["expires_at"] > view["expires_at"]
    stripe.subs[sub]["status"] = "canceled"
    await send(client, "customer.subscription.deleted", {"id": sub, "customer": customer})
    ended = await listed(client, ada.headers)
    assert ended["license_key"] is None and {k["state"] for k in ended["keys"]} == {"revoked"}
    assert (await client.get("/v1/license/keys")).status_code == 401


async def test_no_key_for_a_payment_not_on_the_orgs_live_paying_plan(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Pro")
    await subscribed(engine, ada.org_id, f"sub_now_{ada.org_id.hex}", f"cus_now_{ada.org_id.hex}")
    customer = f"cus_now_{ada.org_id.hex}"
    paid_sub(stripe, f"sub_old_{ada.org_id.hex}", customer, "price_test_pro", PERIOD_END)
    await send(client, "invoice.payment_succeeded", {"customer": customer, "subscription": f"sub_old_{ada.org_id.hex}"})
    paid_sub(stripe, f"sub_now_{ada.org_id.hex}", customer, "price_test_pro", PERIOD_END, "past_due")
    await send(client, "invoice.payment_succeeded", {"customer": customer, "subscription": f"sub_now_{ada.org_id.hex}"})
    eve = await person(engine)
    paid_sub(stripe, f"sub_odd_{eve.org_id.hex}", f"cus_odd_{eve.org_id.hex}", "price_unknown", PERIOD_END)
    odd = {"mode": "subscription", "client_reference_id": str(eve.org_id), "customer": f"cus_odd_{eve.org_id.hex}"}
    await send(client, "checkout.session.completed", odd | {"subscription": f"sub_odd_{eve.org_id.hex}"})  # Free
    meta = {"subscription_details": {"subscription": "sub_x", "metadata": {"org_id": "not-an-org"}}}
    await send(client, "invoice.payment_succeeded", {"customer": "cus_nobody", "parent": meta})
    for who in (ada, eve):
        assert await listed(client, who.headers) == {"license_key": None, "keys": []}


async def test_a_subscription_without_its_period_end_gets_a_months_key(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    sub, customer = f"sub_m_{ada.org_id.hex}", f"cus_m_{ada.org_id.hex}"
    paid_sub(stripe, sub, customer, "price_test_pro", None)
    obj = {"mode": "subscription", "client_reference_id": str(ada.org_id), "customer": customer, "subscription": sub}
    await send(client, "checkout.session.completed", obj)
    expires = datetime.fromisoformat((await listed(client, ada.headers))["keys"][0]["expires_at"])
    assert timedelta(days=30, hours=23) < expires - datetime.now(UTC) <= timedelta(days=31)


async def test_an_enterprise_grant_issues_a_key_through_its_last_day_and_revoking_revokes_it(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada, signer = await person(engine, "Pro"), Ed25519PrivateKey.generate()
    deal = f"sub_ent_{ada.org_id.hex}"
    stripe.sub(deal, f"cus_ent_{ada.org_id.hex}", "price_deal", 1)
    billing = StripeClient(fake_http(stripe), "sk_test")
    await enterprise.grant(engine, billing, ada.org_id, date(2027, 10, 31), deal, signer)
    keys = await listed(client, ada.headers)
    payload = read(keys["license_key"], signer.public_key())
    assert (payload["tier"], payload["max_nodes"], payload["max_precedents"]) == ("enterprise", None, None)
    assert payload["cluster_sync_enabled"] is True and payload["expires_at"] == "2027-11-01T00:00:00Z"
    stripe.subs[deal]["items"]["data"][0]["current_period_end"] = PERIOD_END
    await send(client, "invoice.payment_succeeded", {"customer": f"cus_ent_{ada.org_id.hex}", "subscription": deal})
    assert len((await listed(client, ada.headers))["keys"]) == 1  # the deal's invoice: the same key, to its day
    await enterprise.revoke(engine, ada.org_id)
    assert (await listed(client, ada.headers))["license_key"] is None


async def test_an_expired_key_is_listed_expired_and_not_sent(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    async with engine.begin() as conn:
        await license_keys.issue(conn, Ed25519PrivateKey.generate(), ada.org_id, datetime.now(UTC) - timedelta(days=1))
    keys = await listed(client, ada.headers)
    assert keys["license_key"] is None and keys["keys"][0]["state"] == "expired"


async def test_the_connector_shows_the_key_masked(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    async with engine.begin() as conn:
        key = await license_keys.issue(conn, Ed25519PrivateKey.generate(), ada.org_id, datetime(2027, 2, 1, tzinfo=UTC))
    assert key is not None
    _, auth = await granted(engine, ada)
    said = f"Licence key: {key[:8]}…{key[-6:]} (pro, expires 2027-02-01); copy it on the platform."
    plan = await tool(client, auth, "plan")
    assert plan["content"][0]["text"].splitlines()[-1] == said
    assert plan["structuredContent"]["license_key"] == f"{key[:8]}…{key[-6:]}"
    used = await tool(client, auth, "usage")
    assert said in used["content"][0]["text"] and key not in json.dumps(used)
