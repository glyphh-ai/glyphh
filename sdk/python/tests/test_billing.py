import json

import httpx
import pytest

from glyphh import AsyncGlyphh, Glyphh, GlyphhError

SERVER = "http://localhost:8080"
PLAN = "7f0c7b1e-0000-4000-8000-0000000000cc"
PORTAL = {"url": "https://billing.test/session"}

AT = "2026-10-12T00:00:00+00:00"
PLAN_VIEW = {
    "id": PLAN,
    "family": "Basic",
    "version": 1,
    "name": "Basic v1",
    "price_cents": 4000,
    "max_seats": 25,
    "monthly_credit_cents": 1000,
    "included_machines": 10,
    "extra_machine_cents": 500,
    "on_sale": True,
}
CREDIT = {
    "period_start": AT,
    "period_end": AT,
    "included_cents": 1000,
    "used_cents": 0,
    "bought_cents": 0,
    "balance_cents": 1000,
    "next_expiry_cents": None,
    "next_expiry_at": None,
}
AUTO = {
    "on": False,
    "below_cents": None,
    "to_cents": None,
    "monthly_cap_cents": None,
    "last_at": None,
    "failed_at": None,
    "failure": None,
}
BILLING = {
    "plan": PLAN_VIEW,
    "status": "none",
    "seats_in_use": 1,
    "seats_billed": 0,
    "machines_in_use": 0,
    "extra_machines": 0,
    "card": None,
    "billing_email": None,
    "pending_plan": None,
    "pending_plan_at": None,
    "auto_top_up": AUTO,
    "credit": CREDIT,
    "stripe_publishable_key": "pk",
}
ANSWERS = {
    "plans": [PLAN_VIEW],
    "credit": {"plan": "Basic", "renews_at": None, "credit": CREDIT},
    "get": BILLING,
    "sync": BILLING,
    "add_funds": {"payment_id": PLAN, "amount_cents": 4500, "client_secret": "s", "stripe_publishable_key": "pk"},
    "top_ups": {"top_ups": [], "total": 0},
    "check_auto_top_up": {"charged_cents": None, "reason": "off"},
    "set_up_card": {"client_secret": "s", "stripe_publishable_key": "pk"},
    "preview_plan": {
        "kind": "subscribe",
        "current": PLAN_VIEW,
        "target": PLAN_VIEW,
        "seats": 1,
        "due_now_cents": 4000,
        "next_invoice_cents": 4000,
        "next_invoice_at": None,
        "applies_at": None,
    },
    "change_plan": {"state": "applying"},
    "ledger": {"entries": [], "total": 0},
    "spend_by_day": [{"day": "2026-10-12", "cents": 40}],
    "invoices": {"invoices": [], "has_more": False},
    "next_invoice": {"amount_cents": 100, "at": None, "prorated_cents": 0},
    "portal": PORTAL,
}


def answering(body: object, seen: list, status: int = 200) -> httpx.MockTransport:
    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, content=json.dumps(body).encode(), headers={"content-type": "application/json"})

    return httpx.MockTransport(handle)


CALLS = [
    ("plans", (), "GET", "/v1/plans", "", None),
    ("credit", (), "GET", "/v1/org/credit", "", None),
    ("get", (), "GET", "/v1/org/billing", "", None),
    ("add_funds", (4500,), "POST", "/v1/org/billing/top-ups", "", {"amount_cents": 4500}),
    ("top_ups", (), "GET", "/v1/org/billing/top-ups", "page=1&size=25", None),
    ("check_auto_top_up", (), "POST", "/v1/org/billing/auto-top-up/check", "", None),
    ("set_up_card", (), "POST", "/v1/org/billing/card", "", None),
    ("preview_plan", (PLAN,), "POST", "/v1/org/billing/plan/preview", "", {"plan_id": PLAN}),
    ("change_plan", (PLAN,), "POST", "/v1/org/billing/plan", "", {"plan_id": PLAN}),
    ("sync", (), "POST", "/v1/org/billing/sync", "", None),
    ("ledger", (2, 10), "GET", "/v1/org/billing/ledger", "page=2&size=10", None),
    ("spend_by_day", (), "GET", "/v1/org/billing/spend", "", None),
    ("invoices", ("in_1", 10), "GET", "/v1/org/billing/invoices", "after=in_1&limit=10", None),
    ("invoices", (), "GET", "/v1/org/billing/invoices", "limit=25", None),
    ("next_invoice", (), "GET", "/v1/org/billing/next-invoice", "", None),
    ("portal", (), "POST", "/v1/org/billing/portal", "", None),
]


def _sent(request: httpx.Request) -> tuple:
    body = json.loads(request.content) if request.content else None
    return request.method, request.url.path, request.url.query.decode(), body


@pytest.mark.parametrize(("name", "args", "method", "path", "query", "body"), CALLS)
def test_each_billing_call_reaches_its_route(
    name: str, args: tuple, method: str, path: str, query: str, body: object
) -> None:
    seen: list = []
    answer = getattr(
        Glyphh(
            SERVER, token="t", transport=answering(ANSWERS[name], seen, 201 if name == "add_funds" else 200)
        ).billing,
        name,
    )(*args)
    assert answer == ANSWERS[name]
    assert _sent(seen[0]) == (method, path, query, body)


@pytest.mark.parametrize(("name", "args", "method", "path", "query", "body"), CALLS)
async def test_async_billing_calls_match(
    name: str, args: tuple, method: str, path: str, query: str, body: object
) -> None:
    seen: list = []
    answer = await getattr(
        AsyncGlyphh(
            SERVER, token="t", transport=answering(ANSWERS[name], seen, 201 if name == "add_funds" else 200)
        ).billing,
        name,
    )(*args)
    assert answer == ANSWERS[name] and _sent(seen[0]) == (method, path, query, body)


def test_auto_top_up_lists_and_refusals() -> None:
    seen: list = []
    glyphh = Glyphh(
        SERVER,
        token="t",
        transport=answering(
            {
                "on": True,
                "below_cents": 500,
                "to_cents": 2500,
                "monthly_cap_cents": None,
                "last_at": None,
                "failed_at": None,
                "failure": None,
            },
            seen,
        ),
    )
    assert glyphh.billing.set_auto_top_up(on=True, below_cents=500, to_cents=2500)["on"] is True
    assert json.loads(seen[0].content) == {"on": True, "below_cents": 500, "to_cents": 2500, "monthly_cap_cents": None}
    assert Glyphh(SERVER, token="t", transport=answering(None, [])).billing.next_invoice() is None
    refused = {"error": {"code": "E_FORBIDDEN", "message": "Only an org admin can do that.", "trace_id": "t1"}}
    with pytest.raises(GlyphhError) as e:
        Glyphh(SERVER, token="t", transport=answering(refused, [], 403)).billing.get()
    assert e.value.code == "E_FORBIDDEN"


async def test_async_auto_top_up() -> None:
    glyphh = AsyncGlyphh(SERVER, token="t", transport=answering(AUTO, []))
    answer = await glyphh.billing.set_auto_top_up(on=False, below_cents=500, to_cents=2500, monthly_cap_cents=2000)
    assert answer == AUTO
