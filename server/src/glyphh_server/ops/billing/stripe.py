"""The one Stripe call the webhook needs, over its REST API with httpx, failing closed: anything but a good answer is
Stripe being unavailable. Tests fake Stripe at the HTTP layer; nothing here ever runs against real keys in tests.
The server only reads: it starts no checkout, changes no subscription and reports no usage any more."""

import logging
from typing import Any

import httpx

from glyphh_server.errors import Unavailable
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.stripe")

API: str = "https://api.stripe.com/v1"


class StripeClient:
    def __init__(self, http: httpx.AsyncClient, secret_key: str) -> None:
        if not secret_key:
            raise Unavailable("Billing isn't set up on this server.", reason="billing_off")
        self.http, self.secret_key = http, secret_key

    async def subscription(self, subscription_id: str) -> dict[str, Any]:
        path = f"/subscriptions/{subscription_id}"
        try:
            res = await self.http.get(f"{API}{path}", headers={"authorization": f"Bearer {self.secret_key}"})
            res.raise_for_status()
            return res.json()  # type: ignore[no-any-return]
        except (httpx.HTTPError, ValueError) as err:
            log.warning("stripe call failed", extra=fields(path=path, error=repr(err)))
            raise Unavailable("Stripe didn't answer. Try again.", reason="stripe") from err
