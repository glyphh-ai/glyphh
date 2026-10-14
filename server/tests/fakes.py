"""Google, GitHub and Stripe, faked at the HTTP layer: the server's own code runs unchanged against them, and no
test ever reaches the real services."""

from typing import Any
from urllib.parse import parse_qsl

import httpx

GOOGLE_ME: dict[str, Any] = {
    "sub": "g-pages-1",
    "email": "pages@google.test",
    "email_verified": True,
    "name": "Paige Turner",
    "given_name": "Paige",
    "family_name": "Turner",
}
GITHUB_USER: dict[str, Any] = {"id": 4242, "login": "octo", "name": "Octo Cat", "email": None}
GITHUB_EMAILS: list[dict[str, Any]] = [
    {"email": "other@gh.test", "primary": False, "verified": True},
    {"email": "octo@gh.test", "primary": True, "verified": True},
]


def provider_answers(over: dict[tuple[str, str], Any] | None = None) -> dict[tuple[str, str], Any]:
    return {
        ("POST", "/token"): {"access_token": "g-at"},
        ("GET", "/v1/userinfo"): GOOGLE_ME,
        ("POST", "/login/oauth/access_token"): {"access_token": "gh-at"},
        ("GET", "/user"): GITHUB_USER,
        ("GET", "/user/emails"): GITHUB_EMAILS,
        **(over or {}),
    }


def answer(found: Any) -> httpx.Response:
    return found if isinstance(found, httpx.Response) else httpx.Response(200, json=found)


class FakeStripe:
    """Stripe's few endpoints billing uses, remembering every call and every subscription."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []
        self.subs: dict[str, dict[str, Any]] = {}
        self.fail: bool = False

    def sub(self, sub_id: str, customer: str, price: str, quantity: int, status: str = "active") -> dict[str, Any]:
        self.subs[sub_id] = {
            "id": sub_id,
            "customer": customer,
            "status": status,
            "metadata": {},
            "items": {"data": [{"id": f"si_{sub_id}", "price": {"id": price}, "quantity": quantity}]},
        }
        return self.subs[sub_id]

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            return httpx.Response(500, json={"error": {"message": "down"}})
        body = dict(parse_qsl(request.content.decode()))
        path = request.url.path.removeprefix("/v1")
        self.calls.append((request.method, path, body))
        if path == "/customers":
            return answer({"id": f"cus_{len(self.calls)}"})
        if path == "/checkout/sessions":
            return answer({"id": "cs_1", "url": "https://checkout.stripe.test/cs_1"})
        if path == "/billing_portal/sessions":
            return answer({"url": "https://billing.stripe.test/p_1"})
        sub = self.subs[path.removeprefix("/subscriptions/")]
        item = sub["items"]["data"][0]
        if "items[0][price]" in body:
            item["price"] = {"id": body["items[0][price]"]}
        if "items[0][quantity]" in body:
            item["quantity"] = int(body["items[0][quantity]"])
        return answer(sub)


def fake_http(stripe: FakeStripe | None = None, over: dict[tuple[str, str], Any] | None = None) -> httpx.AsyncClient:
    providers = provider_answers(over)
    billing = stripe or FakeStripe()

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.stripe.com":
            return billing.handle(request)
        return answer(providers[(request.method, request.url.path)])

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))
