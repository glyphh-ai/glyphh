"""Make what Glyphh sells in Stripe, once per Stripe account (test mode, then live), and print the settings to set.

    STRIPE_SECRET_KEY=sk_test_… uv run python scripts/stripe-setup.py

Safe to run again: products have Glyphh's own ids, prices are found by their lookup keys and the meter by its event
name, so nothing is made twice. It makes the products Pro, Team and Hosting; Pro's and Team's flat monthly prices
(from db/seed.py); the Billing Meter glyphh_hosting (summed, one unit a US cent, the customer by its id); and the
hosting price on that meter, a cent a unit, monthly. Enterprise has no price here: each deal is its own. A price
already made is never changed: a plan's lookup key carries its amount, so a new amount in db/seed.py is a new price
(and, once set, a new plan version at the next boot).
"""

import os
import sys
from typing import Any

import httpx

from glyphh_server.db.seed import PLANS
from glyphh_server.ops.billing.stripe import API, form

METER: str = "glyphh_hosting"
HOSTING_KEY: str = "glyphh_hosting_cent"


class Stripe:
    def __init__(self, http: httpx.Client, key: str) -> None:
        self.http, self.headers = http, {"authorization": f"Bearer {key}"}

    def get(self, path: str, **params: Any) -> httpx.Response:
        return self.http.get(f"{API}{path}", params=form(params), headers=self.headers)

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        res = self.http.post(f"{API}{path}", data=form(body), headers=self.headers)
        res.raise_for_status()
        return res.json()


def product(stripe: Stripe, product_id: str, name: str) -> str:
    if stripe.get(f"/products/{product_id}").status_code == 404:
        stripe.post("/products", {"id": product_id, "name": name})
    return product_id


def price(stripe: Stripe, lookup_key: str, body: dict[str, Any]) -> str:
    found = stripe.get("/prices", lookup_keys=[lookup_key], active=True)
    found.raise_for_status()
    if found.json()["data"]:
        return str(found.json()["data"][0]["id"])
    return str(stripe.post("/prices", {**body, "lookup_key": lookup_key, "currency": "usd"})["id"])


def meter(stripe: Stripe) -> str:
    listed = stripe.get("/billing/meters", status="active", limit=100)
    listed.raise_for_status()
    found = [m for m in listed.json()["data"] if m["event_name"] == METER]
    if found:
        return str(found[0]["id"])
    body = {
        "display_name": "Glyphh hosting (cents)",
        "event_name": METER,
        "default_aggregation": {"formula": "sum"},
        "customer_mapping": {"type": "by_id", "event_payload_key": "stripe_customer_id"},
        "value_settings": {"event_payload_key": "value"},
    }
    return str(stripe.post("/billing/meters", body)["id"])


def setup(stripe: Stripe) -> dict[str, str]:
    """Everything made or found: the settings to set, by name."""
    settings: dict[str, str] = {}
    for plan in PLANS:
        if not plan.self_serve or plan.interval is None:
            continue
        made = product(stripe, f"glyphh_{plan.name.lower()}", f"Glyphh {plan.name}")
        recurring = {"interval": plan.interval}
        key = f"glyphh_{plan.name.lower()}_{plan.interval}_{plan.price_cents}"
        body = {"product": made, "unit_amount": plan.price_cents, "recurring": recurring}
        settings[f"GLYPHH_STRIPE_PRICE_{plan.name.upper()}"] = price(stripe, key, body)
    hosting = product(stripe, "glyphh_hosting", "Glyphh hosting")
    recurring = {"interval": "month", "usage_type": "metered", "meter": meter(stripe)}
    body = {"product": hosting, "unit_amount": 1, "recurring": recurring}
    settings["GLYPHH_STRIPE_PRICE_HOSTING"] = price(stripe, HOSTING_KEY, body)
    settings["GLYPHH_STRIPE_METER_HOSTING"] = METER
    return settings


def main() -> None:
    key = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("GLYPHH_STRIPE_SECRET_KEY")
    if not key:
        sys.exit("Set STRIPE_SECRET_KEY to the Stripe account's secret key (sk_test_… or sk_live_…).")
    with httpx.Client(timeout=30) as http:
        settings = setup(Stripe(http, key))
    print("Set these on the server (and GLYPHH_STRIPE_WEBHOOK_SECRET from the webhook endpoint):\n")
    for name, value in settings.items():
        print(f"{name}={value}")
    print("\nOn Fly: fly secrets set " + " ".join(f"{name}={value}" for name, value in settings.items()))


if __name__ == "__main__":
    main()
