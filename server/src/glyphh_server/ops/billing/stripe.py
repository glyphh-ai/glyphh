"""The few Stripe calls billing needs, over its REST API with httpx, failing closed: anything but a good answer is
Stripe being unavailable. Tests fake Stripe at the HTTP layer; nothing here ever runs against real keys in tests."""

import logging
from typing import Any

import httpx

from glyphh_server.errors import Unavailable
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.stripe")

API: str = "https://api.stripe.com/v1"


def form(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Stripe's form encoding: nested keys as a[b][c], lists as a[0][b], booleans as true and false."""
    flat: dict[str, str] = {}
    for key, value in data.items():
        name = f"{prefix}[{key}]" if prefix else str(key)
        if isinstance(value, dict):
            flat.update(form(value, name))
        elif isinstance(value, list):
            flat.update(form(dict(enumerate(value)), name))
        elif isinstance(value, bool):
            flat[name] = str(value).lower()
        else:
            flat[name] = str(value)
    return flat


class StripeClient:
    def __init__(self, http: httpx.AsyncClient, secret_key: str) -> None:
        if not secret_key:
            raise Unavailable("Billing isn't set up on this server.", reason="billing_off")
        self.http, self.secret_key = http, secret_key

    async def call(self, method: str, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """A call to Stripe; a DELETE's parameters ride the query, as Stripe reads them."""
        sent = {"params" if method == "DELETE" else "data": form(data or {})}
        try:
            res = await self.http.request(
                method, f"{API}{path}", **sent, headers={"authorization": f"Bearer {self.secret_key}"}
            )
            res.raise_for_status()
            return res.json()
        except (httpx.HTTPError, ValueError) as err:
            log.warning("stripe call failed", extra=fields(path=path, error=repr(err)))
            raise Unavailable("Stripe didn't answer. Try again.", reason="stripe") from err

    async def create_customer(self, email: str, name: str, org_id: str) -> str:
        made = await self.call("POST", "/customers", {"email": email, "name": name, "metadata": {"org_id": org_id}})
        return str(made["id"])

    async def checkout(self, customer: str, lines: list[dict[str, Any]], org_id: str, return_url: str) -> str:
        """Checkout for a subscription of these lines: the plan's flat price, and the metered hosting price."""
        session = await self.call(
            "POST",
            "/checkout/sessions",
            {
                "mode": "subscription",
                "customer": customer,
                "client_reference_id": org_id,
                "line_items": lines,
                "subscription_data": {"metadata": {"org_id": org_id}},
                "success_url": return_url,
                "cancel_url": return_url,
            },
        )
        return str(session["url"])

    async def subscription(self, subscription_id: str) -> dict[str, Any]:
        return await self.call("GET", f"/subscriptions/{subscription_id}")

    async def change(self, subscription_id: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Change the subscription's items (an item's price, a new item), prorated."""
        body = {"items": items, "proration_behavior": "create_prorations"}
        return await self.call("POST", f"/subscriptions/{subscription_id}", body)

    async def cancel(self, subscription_id: str) -> dict[str, Any]:
        """Cancel the subscription now: what is owed (the unused time credited) invoiced at once."""
        return await self.call("DELETE", f"/subscriptions/{subscription_id}", {"invoice_now": True, "prorate": True})

    async def portal(self, customer: str, return_url: str) -> str:
        session = await self.call("POST", "/billing_portal/sessions", {"customer": customer, "return_url": return_url})
        return str(session["url"])
