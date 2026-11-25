"""The Stripe client: Stripe's form encoding, and failing closed."""

import httpx
import pytest

from glyphh_server.errors import Unavailable
from glyphh_server.ops.billing.stripe import StripeClient, form


def test_nested_values_are_encoded_the_way_stripe_reads_them() -> None:
    assert form({"a": 1, "b": {"c": "d"}, "items": [{"price": "p", "quantity": 2}]}) == {
        "a": "1",
        "b[c]": "d",
        "items[0][price]": "p",
        "items[0][quantity]": "2",
    }


async def test_an_answer_that_is_not_json_is_unavailable() -> None:
    http = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>")))
    with pytest.raises(Unavailable):
        await StripeClient(http, "sk_test_x").subscription("sub_1")


def test_without_a_key_billing_is_off() -> None:
    with pytest.raises(Unavailable) as off:
        StripeClient(httpx.AsyncClient(), "")
    assert off.value.detail == {"reason": "billing_off"}
