"""Google, GitHub (sign-in) and Stripe, faked at the HTTP layer: the server's own code runs unchanged against them,
and no test ever reaches the real services."""

from typing import Any

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
    """Stripe's one endpoint the webhook reads, a subscription by its id, remembering every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.subs: dict[str, dict[str, Any]] = {}
        self.fail: bool = False

    def sub(self, sub_id: str, customer: str, price: str, quantity: int = 1, status: str = "active") -> dict[str, Any]:
        self.subs[sub_id] = {
            "id": sub_id,
            "customer": customer,
            "status": status,
            "metadata": {},
            "items": {"data": [{"id": f"si_{sub_id}", "price": {"id": price}, "quantity": quantity}]},
        }
        return self.subs[sub_id]

    def add_item(self, sub_id: str, price: str) -> dict[str, Any]:
        """A metered item, as Ada Cloud's reads' price was: it has no quantity."""
        item = {"id": f"si_{sub_id}_{price}", "price": {"id": price, "recurring": {"usage_type": "metered"}}}
        self.subs[sub_id]["items"]["data"].append(item)
        return item

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            return httpx.Response(500, json={"error": {"message": "down"}})
        path = request.url.path.removeprefix("/v1")
        self.calls.append((request.method, path))
        return answer(self.subs[path.removeprefix("/subscriptions/")])


def fake_http(stripe: FakeStripe | None = None, over: dict[tuple[str, str], Any] | None = None) -> httpx.AsyncClient:
    providers = provider_answers(over)
    billing = stripe or FakeStripe()

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.stripe.com":
            return billing.handle(request)
        return answer(providers[(request.method, request.url.path)])

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))
