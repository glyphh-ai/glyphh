"""The card on file and the invoices, read from a fake Stripe, and the portal opened at its card page."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.db.helpers import member, org_row, person, subscribed
from tests.fakes import FakeStripe

VISA = {"brand": "visa", "last4": "4242", "exp_month": 4, "exp_year": 2029}
INVOICE = {
    "id": "in_1",
    "number": "GLY-0001",
    "status": "paid",
    "total": 9_900,
    "currency": "usd",
    "created": 1_763_683_200,
    "hosted_invoice_url": "https://invoice.stripe.test/in_1",
    "invoice_pdf": "https://invoice.stripe.test/in_1.pdf",
}


async def test_an_org_that_never_paid_has_no_card_and_stripe_is_not_asked(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    res = await client.get("/v1/billing/payment", headers=ada.headers)
    assert res.json() == {"card": None, "invoices": []} and stripe.calls == []


async def test_the_default_card_and_the_invoices_are_shown(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Pro")
    await subscribed(engine, ada.org_id, "sub_card", "cus_card")
    stripe.reads["/customers/cus_card"] = {"invoice_settings": {"default_payment_method": {"card": VISA}}}
    stripe.reads["/invoices"] = {"data": [INVOICE, {"id": "in_2", "created": 1_763_000_000}]}
    shown = (await client.get("/v1/billing/payment", headers=ada.headers)).json()
    assert shown["card"] == VISA
    assert shown["invoices"][0] == {
        "id": "in_1",
        "number": "GLY-0001",
        "status": "paid",
        "total_cents": 9_900,
        "currency": "usd",
        "created": "2025-11-21T00:00:00Z",
        "url": "https://invoice.stripe.test/in_1",
        "pdf": "https://invoice.stripe.test/in_1.pdf",
    }
    assert shown["invoices"][1] | {"created": None} == {
        "id": "in_2",
        "number": None,
        "status": "draft",
        "total_cents": 0,
        "currency": "usd",
        "created": None,
        "url": None,
        "pdf": None,
    }
    asked = [(method, path) for method, path, _ in stripe.calls]
    assert asked == [("GET", "/customers/cus_card"), ("GET", "/invoices")]
    assert stripe.calls[0][2] == {"expand[0]": "invoice_settings.default_payment_method"}
    assert stripe.calls[1][2] == {"customer": "cus_card", "limit": "12"}


async def test_without_a_default_the_newest_card_or_none(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine, "Pro")
    await subscribed(engine, ada.org_id, "sub_none", "cus_none")
    stripe.reads["/customers/cus_none"] = {"invoice_settings": {"default_payment_method": "pm_not_expanded"}}
    stripe.reads["/customers/cus_none/payment_methods"] = {"data": [{"card": VISA | {"brand": "amex"}}]}
    stripe.reads["/invoices"] = {"data": []}
    shown = (await client.get("/v1/billing/payment", headers=ada.headers)).json()
    assert shown["card"]["brand"] == "amex" and stripe.calls[1][2] == {"type": "card", "limit": "1"}
    stripe.reads["/customers/cus_none"] = {}
    stripe.reads["/customers/cus_none/payment_methods"] = {"data": []}
    assert (await client.get("/v1/billing/payment", headers=ada.headers)).json()["card"] is None


async def test_the_card_page_makes_the_customer_first(
    client: httpx.AsyncClient, engine: AsyncEngine, stripe: FakeStripe
) -> None:
    ada = await person(engine)
    res = await client.post("/v1/billing/card", headers=ada.headers)
    assert res.json() == {"url": "https://billing.stripe.test/p_1"}
    customer = (await org_row(engine, ada.org_id)).stripe_customer_id
    assert customer is not None and stripe.calls[0][1] == "/customers"
    assert stripe.calls[-1][2] == {
        "customer": customer,
        "return_url": "http://localhost:8080/billing/done",
        "flow_data[type]": "payment_method_update",
    }
    await client.post("/v1/billing/card", headers=ada.headers)
    assert [path for _, path, _ in stripe.calls].count("/customers") == 1


async def test_the_card_is_the_admins(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    bob = await member(engine, ada.org_id)
    assert (await client.get("/v1/billing/payment", headers=bob.headers)).status_code == 403
    assert (await client.post("/v1/billing/card", headers=bob.headers)).status_code == 403
