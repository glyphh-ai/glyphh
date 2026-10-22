"""scripts/stripe-setup.py against a fake Stripe: the products, the plans' flat prices, the meter and its metered
price made once, found by their ids, lookup keys and event name when run again, and the settings printed."""

import runpy
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

import httpx
import pytest

SCRIPT: Path = Path(__file__).resolve().parent.parent / "scripts" / "stripe-setup.py"


class Account:
    """A Stripe account's products, prices and meters, as the script sees them."""

    def __init__(self) -> None:
        self.products: set[str] = set()
        self.prices: list[dict[str, str]] = []
        self.meters: list[dict[str, str]] = []
        self.made: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer sk_test_setup"
        path, body = request.url.path.removeprefix("/v1"), dict(parse_qsl(request.content.decode()))
        query = dict(parse_qsl(request.url.query.decode()))
        if request.method == "POST":
            self.made.append(path)
        if path.startswith("/products/"):
            return httpx.Response(200 if path.split("/")[-1] in self.products else 404, json={})
        if path == "/products":
            self.products.add(body["id"])
            return httpx.Response(200, json={"id": body["id"]})
        if path == "/prices" and request.method == "GET":
            found = [p for p in self.prices if p["lookup_key"] == query["lookup_keys[0]"]]
            return httpx.Response(200, json={"data": found})
        if path == "/prices":
            self.prices.append({**body, "id": f"price_{len(self.prices) + 1}"})
            return httpx.Response(200, json=self.prices[-1])
        if path == "/billing/meters" and request.method == "GET":
            return httpx.Response(200, json={"data": self.meters})
        self.meters.append({**body, "id": "mtr_1"})
        return httpx.Response(200, json=self.meters[-1])


def _script() -> dict[str, Any]:
    return runpy.run_path(str(SCRIPT), run_name="stripe_setup")


def test_it_makes_everything_once_and_finds_it_again() -> None:
    account, script = Account(), _script()
    with httpx.Client(transport=httpx.MockTransport(account.handle)) as http:
        stripe = script["Stripe"](http, "sk_test_setup")
        first = script["setup"](stripe)
        made = list(account.made)
        assert script["setup"](stripe) == first and account.made == made  # again: nothing new
    assert first == {
        "GLYPHH_STRIPE_PRICE_BASIC": "price_1",
        "GLYPHH_STRIPE_PRICE_PRO": "price_2",
        "GLYPHH_STRIPE_PRICE_TEAM": "price_3",
        "GLYPHH_STRIPE_PRICE_HOSTING": "price_4",
        "GLYPHH_STRIPE_METER_HOSTING": "glyphh_hosting",
        "GLYPHH_STRIPE_PRICE_ADA": "price_5",
        "GLYPHH_STRIPE_METER_ADA": "ada_requests",
    }
    products = {"glyphh_basic", "glyphh_pro", "glyphh_team", "glyphh_hosting", "glyphh_ada_requests"}
    assert account.products == products
    basic, pro, team, hosting, reads = account.prices
    assert (basic["unit_amount"], basic["product"], basic["lookup_key"]) == (
        "2000",
        "glyphh_basic",
        "glyphh_basic_month_2000",
    )
    assert (reads["unit_amount_decimal"], reads["recurring[usage_type]"], reads["lookup_key"]) == (
        "0.01",
        "metered",
        "glyphh_ada_requests_10k_100",
    )  # a hundredth of a cent a read: $1 per 10,000
    assert (pro["unit_amount"], pro["recurring[interval]"], pro["lookup_key"]) == (
        "9900",
        "month",
        "glyphh_pro_month_9900",
    )
    assert (team["unit_amount"], team["product"], team["currency"]) == ("29900", "glyphh_team", "usd")
    assert (hosting["unit_amount"], hosting["recurring[usage_type]"], hosting["recurring[meter]"]) == (
        "1",
        "metered",
        "mtr_1",
    )
    meter, ada = account.meters
    assert (ada["event_name"], ada["display_name"]) == ("ada_requests", "Ada Cloud reads")
    assert (meter["event_name"], meter["default_aggregation[formula]"]) == ("glyphh_hosting", "sum")
    assert (meter["customer_mapping[event_payload_key]"], meter["value_settings[event_payload_key]"]) == (
        "stripe_customer_id",
        "value",
    )


def test_it_needs_a_key_and_prints_the_settings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("GLYPHH_STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(SystemExit, match="Set STRIPE_SECRET_KEY"):
        runpy.run_path(str(SCRIPT), run_name="__main__")
    account = Account()
    real = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real(transport=httpx.MockTransport(account.handle), **kw))
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_setup")
    runpy.run_path(str(SCRIPT), run_name="__main__")
    out = capsys.readouterr().out
    assert "GLYPHH_STRIPE_PRICE_BASIC=price_1\n" in out and "GLYPHH_STRIPE_METER_HOSTING=glyphh_hosting\n" in out
    assert "fly secrets set GLYPHH_STRIPE_PRICE_BASIC=price_1 GLYPHH_STRIPE_PRICE_PRO=price_2" in out
