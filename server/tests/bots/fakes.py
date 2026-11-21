"""Pipedream and Claude, faked: Pipedream at the HTTP layer (the server's own client calls it unchanged), Claude as
an AsyncAnthropic whose beta.messages.create answers the turns a test scripted, remembering every request."""

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qsl

import httpx

PROJECT: str = "proj_test"
CONNECT: str = f"/v1/connect/{PROJECT}"
GMAIL: dict[str, Any] = {"name_slug": "gmail", "name": "Gmail", "description": "Email by Google", "img_src": "g.png"}
SLACK: dict[str, Any] = {"name_slug": "slack", "name": "Slack", "description": "Chat", "img_src": "s.png"}
SEND: dict[str, Any] = {
    "key": "gmail-send-email",
    "name": "Send Email",
    "description": "Send an email from your Gmail account",
    "configurable_props": [
        {"name": "gmail", "type": "app", "app": "gmail"},
        {"name": "to", "type": "string[]", "label": "To"},
        {"name": "subject", "type": "string", "label": "Subject"},
        {"name": "body", "type": "string", "label": "Body", "optional": True},
        {"name": "format", "type": "string", "options": ["text", "html"], "optional": True},
        {"name": "note", "type": "alert", "content": "Shown, not filled in"},
    ],
}
FIND: dict[str, Any] = {
    "key": "gmail-find-email",
    "name": "Find Email",
    "description": "Find emails",
    "configurable_props": [{"name": "gmail", "type": "app", "app": "gmail"}, {"name": "q", "type": "string"}],
}


def account(account_id: str, app: dict[str, Any] = GMAIL, name: str = "ada@gmail.test") -> dict[str, Any]:
    return {"id": account_id, "name": name, "app": app, "healthy": True, "dead": False}


class FakePipedream:
    """Connect's endpoints the server uses: the project's token, Connect tokens, the external user's accounts, the
    apps, an app's actions, a component and running an action. Every call is remembered."""

    def __init__(self) -> None:
        self.accounts: list[dict[str, Any]] = []
        self.calls: list[tuple[str, str, Any]] = []
        self.runs: list[dict[str, Any]] = []
        self.fail_run: bool = False
        # past the token: "down" answers 500, "broken" never answers, "garbled" runs an action answering no JSON,
        # "refusing" refuses a deletion
        self.mode: str = ""

    def _body(self, request: httpx.Request) -> Any:
        return json.loads(request.content) if request.content else None

    def handle(self, request: httpx.Request) -> httpx.Response:
        path, method, body = request.url.path, request.method, self._body(request)
        query = dict(parse_qsl(request.url.query.decode()))
        self.calls.append((method, path, body or query))
        if path == "/v1/oauth/token":
            return httpx.Response(200, json={"access_token": "pd-at", "expires_in": 3600})
        assert request.headers["authorization"] == "Bearer pd-at", "a call without the project's token"
        if self.mode == "down":
            return httpx.Response(500, text="Pipedream is down")
        if self.mode == "broken":
            raise httpx.ConnectError("no route", request=request)
        if self.mode == "garbled" and path.endswith("/actions/run"):
            return httpx.Response(200, text="<html>not json</html>")
        if self.mode == "refusing" and method == "DELETE":
            return httpx.Response(403, json={"error": "not allowed"})
        return self._connect(method, path, body, query)

    def _connect(self, method: str, path: str, body: Any, query: dict[str, str]) -> httpx.Response:
        if (method, path) == ("POST", f"{CONNECT}/tokens"):
            link = "https://pipedream.com/_static/connect.html?token=ctok_1"
            return httpx.Response(
                200, json={"token": "ctok_1", "expires_at": "2026-11-21T12:00:00Z", "connect_link_url": link}
            )
        if (method, path) == ("GET", f"{CONNECT}/accounts"):
            return httpx.Response(200, json={"data": self.accounts})
        if method == "DELETE" and path.startswith(f"{CONNECT}/accounts/"):
            gone = path.rsplit("/", 1)[1]
            if all(a["id"] != gone for a in self.accounts):
                return httpx.Response(404, json={"error": "no such account"})
            self.accounts = [a for a in self.accounts if a["id"] != gone]
            return httpx.Response(204)
        if (method, path) == ("GET", "/v1/apps"):
            found = [a for a in (GMAIL, SLACK) if query.get("q", "").lower() in a["name"].lower()]
            return httpx.Response(200, json={"data": found, "page_info": {"end_cursor": "c1"}})
        if (method, path) == ("GET", f"{CONNECT}/actions"):
            return httpx.Response(200, json={"data": [SEND, FIND] if query.get("app") == "gmail" else []})
        if method == "GET" and path.startswith(f"{CONNECT}/components/"):
            key = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={"data": {SEND["key"]: SEND, FIND["key"]: FIND}[key]})
        if (method, path) == ("POST", f"{CONNECT}/actions/run"):
            self.runs.append(body)
            if self.fail_run:
                return httpx.Response(400, json={"error": "the account's token was revoked"})
            return httpx.Response(200, json={"exports": {"$summary": "Sent"}, "ret": {"id": "msg_1"}})
        return httpx.Response(404, json={"error": f"no fake for {method} {path}"})


def pipedream_http(pd: FakePipedream) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(pd.handle))


def text(said: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=said)


def use(name: str, given: dict[str, Any], use_id: str = "tu_1") -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=use_id, name=name, input=given)


def reply(*content: Any, stop: str = "end_turn", model: str = "claude-opus-5-5", tokens: tuple[int, int] = (1000, 200)):
    usage = SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1])
    return SimpleNamespace(content=list(content), stop_reason=stop, model=model, usage=usage, stop_details=None)


class FakeClaude:
    """beta.messages.create answering the scripted replies in turn (the last one again once they run out)."""

    def __init__(self, *replies: Any) -> None:
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))
        self.raises: BaseException | None = None  # raised by every request instead
        self.hold: asyncio.Event | None = None  # a request waits for it to be set
        self.closed = False

    async def create(self, **sent: Any) -> Any:
        self.requests.append({**sent, "messages": list(sent["messages"])})
        if self.hold is not None:
            await self.hold.wait()
        if self.raises is not None:
            raise self.raises
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]

    async def close(self) -> None:
        self.closed = True
