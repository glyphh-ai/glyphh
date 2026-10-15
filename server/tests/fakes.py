"""Google, GitHub (sign-in and the Glyphh GitHub App), Stripe and Anthropic's routines, faked at the HTTP layer: the
server's own code runs unchanged against them, and no test ever reaches the real services."""

import base64
import json
import uuid
from typing import Any
from urllib.parse import parse_qsl

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

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


def _items(body: dict[str, str], prefix: str = "items") -> list[dict[str, str]]:
    """Stripe's form-encoded items (items[0][price], …) back into a list."""
    found: dict[int, dict[str, str]] = {}
    for key, value in body.items():
        if key.startswith(f"{prefix}["):
            index, name = key.removeprefix(f"{prefix}[").rstrip("]").split("][")
            found.setdefault(int(index), {})[name] = value
    return [found[i] for i in sorted(found)]


class FakeStripe:
    """Stripe's few endpoints billing uses, remembering every call and every subscription: items changed, added and
    deleted as Stripe does, and preview invoices whose proration lines are half a month of each item changed."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []
        self.subs: dict[str, dict[str, Any]] = {}
        self.prices: dict[str, int] = {}
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

    def add_item(self, sub_id: str, price: str, quantity: int) -> dict[str, Any]:
        item = {"id": f"si_{sub_id}_{price}", "price": {"id": price}, "quantity": quantity}
        self.subs[sub_id]["items"]["data"].append(item)
        return item

    def _change(self, sub: dict[str, Any], body: dict[str, str]) -> dict[str, Any]:
        data = sub["items"]["data"]
        for change in _items(body):
            if "id" not in change:
                data.append({"id": f"si_{uuid.uuid4().hex}", "price": {"id": change["price"]}})
                change["id"] = data[-1]["id"]
            item = next(i for i in data if i["id"] == change["id"])
            if change.get("deleted") == "true":
                data.remove(item)
                continue
            if "price" in change:
                item["price"] = {"id": change["price"]}
                item["quantity"] = int(change.get("quantity", 1))
            if "quantity" in change:
                item["quantity"] = int(change["quantity"])
        return sub

    def _preview(self, body: dict[str, str]) -> dict[str, Any]:
        """A new item's half month is a new-style proration line, a deleted one's credit an old-style one; the next
        month's own line is no proration."""
        sub = self.subs[body["subscription"]]
        lines: list[dict[str, Any]] = [
            {"amount": 999_999, "parent": {"subscription_item_details": {"proration": False}}}
        ]
        for change in _items(body, "subscription_details[items]"):
            if "id" in change:
                item = next(i for i in sub["items"]["data"] if i["id"] == change["id"])
                lines.append(
                    {"amount": -self.prices.get(item["price"]["id"], 0) * item["quantity"] // 2, "proration": True}
                )
            else:
                half = self.prices.get(change["price"], 0) * int(change["quantity"]) // 2
                lines.append({"amount": half, "parent": {"subscription_item_details": {"proration": True}}})
        return {"object": "invoice", "currency": "usd", "lines": {"data": lines}}

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            return httpx.Response(500, json={"error": {"message": "down"}})
        body = dict(parse_qsl(request.content.decode()))
        path = request.url.path.removeprefix("/v1")
        self.calls.append((request.method, path, body))
        if path == "/customers":
            return answer({"id": f"cus_{uuid.uuid4().hex}"})
        if path == "/checkout/sessions":
            return answer({"id": "cs_1", "url": "https://checkout.stripe.test/cs_1"})
        if path == "/billing_portal/sessions":
            return answer({"url": "https://billing.stripe.test/p_1"})
        if path == "/invoices/create_preview":
            return answer(self._preview(body))
        sub = self.subs[path.removeprefix("/subscriptions/")]
        return answer(self._change(sub, body) if request.method == "POST" else sub)


def _unb64(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


class FakeGitHubApp:
    """GitHub's App API: each call's JWT checked against the App's public key, installations by id."""

    def __init__(self, public_key: rsa.RSAPublicKey, app_id: str) -> None:
        self.public_key, self.app_id = public_key, app_id
        self.installations: dict[int, dict[str, Any]] = {}
        self.calls: list[tuple[str, str, Any]] = []
        self.fail: bool = False

    def install(self, installation_id: int, account_id: int, login: str) -> None:
        self.installations[installation_id] = {"id": account_id, "login": login, "type": "User"}

    def _claims(self, request: httpx.Request) -> dict[str, Any]:
        head, body, sig = request.headers["authorization"].removeprefix("Bearer ").split(".")
        self.public_key.verify(_unb64(sig), f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
        return json.loads(_unb64(body))

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.fail:
            return httpx.Response(502, text="bad gateway")
        assert self._claims(request)["iss"] == self.app_id
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, body))
        installation_id = int(request.url.path.split("/")[3])
        if installation_id not in self.installations:
            return httpx.Response(404, json={"message": "Not Found"})
        if request.method == "GET":
            return answer({"id": installation_id, "account": self.installations[installation_id]})
        return httpx.Response(201, json={"token": "ghs_fake_repo_token", "expires_at": "2026-10-14T13:00:00Z"})


class FakeRoutines:
    """Anthropic's routine fire endpoint: what it was sent, and the answer it is set to give."""

    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.reply: httpx.Response | Exception = httpx.Response(
            200,
            json={
                "type": "routine_fire",
                "claude_code_session_id": "session_fake",
                "claude_code_session_url": "https://claude.ai/code/session_fake",
            },
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def fake_http(
    stripe: FakeStripe | None = None,
    over: dict[tuple[str, str], Any] | None = None,
    github_app: FakeGitHubApp | None = None,
    routines: FakeRoutines | None = None,
) -> httpx.AsyncClient:
    providers = provider_answers(over)
    billing = stripe or FakeStripe()

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.stripe.com":
            return billing.handle(request)
        if request.url.host == "api.github.com" and request.url.path.startswith("/app/") and github_app:
            return github_app.handle(request)
        if request.url.host == "api.anthropic.com" and routines:
            return routines.handle(request)
        return answer(providers[(request.method, request.url.path)])

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))
