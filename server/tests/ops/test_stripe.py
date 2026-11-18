"""The Stripe client: one read, a subscription by its id, failing closed."""

import httpx
import pytest

from glyphh_server.errors import Unavailable
from glyphh_server.ops.billing.stripe import StripeClient


def _stripe(answer: httpx.Response | Exception, seen: list[httpx.Request] | None = None) -> StripeClient:
    def handle(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if isinstance(answer, Exception):
            raise answer
        return answer

    return StripeClient(httpx.AsyncClient(transport=httpx.MockTransport(handle)), "sk_test_x")


async def test_a_subscription_is_read_by_its_id_with_the_secret_key() -> None:
    seen: list[httpx.Request] = []
    sub = {"id": "sub_1", "status": "active"}
    assert await _stripe(httpx.Response(200, json=sub), seen).subscription("sub_1") == sub
    assert [(r.method, str(r.url)) for r in seen] == [("GET", "https://api.stripe.com/v1/subscriptions/sub_1")]
    assert seen[0].headers["authorization"] == "Bearer sk_test_x"


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(200, text="<html>"),
        httpx.Response(404, json={"error": {"message": "No such subscription"}}),
        httpx.Response(500),
        httpx.ConnectError("no route"),
    ],
)
async def test_anything_but_a_good_answer_is_unavailable(answer: httpx.Response | Exception) -> None:
    with pytest.raises(Unavailable) as down:
        await _stripe(answer).subscription("sub_1")
    assert down.value.detail == {"reason": "stripe"} and "sk_test_x" not in down.value.message


def test_without_a_key_billing_is_off() -> None:
    with pytest.raises(Unavailable) as off:
        StripeClient(httpx.AsyncClient(), "")
    assert off.value.detail == {"reason": "billing_off"}
