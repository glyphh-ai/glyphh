"""Pipedream, Ada and Claude, faked: Pipedream at the HTTP layer (the server's own client calls it unchanged), Ada as
the SDK's client in memory (models, precedents, decisions), and Claude as an anthropic.Anthropic whose
messages.stream answers the texts a test scripted, remembering every request."""

import json
from collections import defaultdict
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qsl

import httpx
from glyphh.client import Decision, ModelInfo
from glyphh.errors import ModelMissingError

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
MAIL: list[dict[str, Any]] = [{"id": "m1", "subject": "Lunch on Friday?"}, {"id": "m2", "subject": "You won!"}]


def account(account_id: str, app: dict[str, Any] = GMAIL, name: str = "ada@gmail.test") -> dict[str, Any]:
    return {"id": account_id, "name": name, "app": app, "healthy": True, "dead": False}


class FakePipedream:
    """Connect's endpoints the server uses: the project's token, Connect tokens, the external user's accounts, the
    apps, an app's actions, a component and running an action. Every call is remembered."""

    def __init__(self) -> None:
        self.accounts: list[dict[str, Any]] = []
        self.calls: list[tuple[str, str, Any]] = []
        self.runs: list[dict[str, Any]] = []
        self.mail: list[dict[str, Any]] = list(MAIL)
        self.fail_run: bool = False
        # past the token: "down" answers 500, "broken" never answers, "refusing" refuses a deletion
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
        if self.mode == "refusing" and method == "DELETE":
            return httpx.Response(403, json={"error": "not allowed"})
        return self._connect(method, path, body, query)

    def _run(self, body: Any) -> httpx.Response:
        self.runs.append(body)
        if self.fail_run:
            return httpx.Response(400, json={"error": "the account's token was revoked"})
        if body["id"] == FIND["key"]:
            return httpx.Response(200, json={"exports": {"$summary": "Found"}, "ret": {"messages": self.mail}})
        return httpx.Response(200, json={"exports": {"$summary": "Sent"}, "ret": {"id": "msg_1"}})

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
            return self._run(body)
        return httpx.Response(404, json={"error": f"no fake for {method} {path}"})


def pipedream_http(pd: FakePipedream) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(pd.handle))


class FakeModel:
    def __init__(self, ada: "FakeAda", name: str) -> None:
        self.ada, self.name = ada, name

    def _there(self) -> None:
        if self.name not in self.ada.specs:
            raise ModelMissingError("E_MODEL_MISSING", f"no model {self.name}", 404)

    def info(self) -> ModelInfo:
        self._there()
        return ModelInfo({"name": self.name, "precedents": len(self.ada.cases[self.name])})

    def record(self, data: dict[str, Any], outcome: str | None = None) -> SimpleNamespace:
        self._there()
        self.ada.cases[self.name].append((data, outcome))
        return SimpleNamespace(data={"id": f"p{len(self.ada.cases[self.name])}"})

    def record_many(self, cases: list[dict[str, Any]]) -> dict[str, Any]:
        for c in cases:
            self.record(c["data"], c.get("outcome"))
        return {"added": len(cases), "precedents": len(self.ada.cases[self.name])}

    def decide(self, data: dict[str, Any]) -> Decision:
        self._there()
        if self.name in self.ada.rule:
            outcome, p = self.ada.rule[self.name](data)
            near = self.ada.near.get(self.name, lambda c: 1.0)(data)
            receipts = [{"id": "p1", "sim": near, "outcome": outcome}]
            return Decision.of(
                {"outcome": outcome, "probabilities": {outcome: p}, "ask": p < 0.7, "receipts": receipts}, self.name
            )
        return Decision.of({"outcome": None, "probabilities": {}, "ask": True}, self.name)

    def facts(self, data: dict[str, Any], top: int | None = None) -> SimpleNamespace:
        self._there()
        return SimpleNamespace(data=[])


class FakeAda:
    """Ada Cloud in memory, as the SDK's client is: `rule[model] = f(case) -> (outcome, p)` decides each case (asking
    under 0.7); else it asks. `keys` are the Ada keys it was reached with."""

    def __init__(self) -> None:
        self.specs: dict[str, dict[str, Any]] = {}
        self.cases: dict[str, list[tuple[dict[str, Any], Any]]] = defaultdict(list)
        self.rule: dict[str, Callable[[dict[str, Any]], tuple[str, float]]] = {}
        self.near: dict[str, Callable[[dict[str, Any]], float]] = {}  # the nearest precedent's sim (else 1)
        self.keys: list[str] = []

    def models(self) -> list[ModelInfo]:
        return [ModelInfo({"name": n, "precedents": len(self.cases[n])}) for n in self.specs]

    def model(self, name: str) -> FakeModel:
        return FakeModel(self, name)

    def create_model(self, name: str, spec: dict[str, Any]) -> FakeModel:
        self.specs[name] = spec
        return FakeModel(self, name)

    def outcomes(self, name: str) -> list[Any]:
        return [o for _, o in self.cases[name]]


class Stream:
    def __init__(self, message: Any) -> None:
        self.message = message

    def __enter__(self) -> "Stream":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def get_final_message(self) -> Any:
        return self.message


class FakeAnthropic:
    """anthropic.Anthropic, faked: messages.stream answers the scripted texts in turn (the last again once they run
    out), each with `tokens`; `fail` is raised instead; every request is kept with the key it came on."""

    def __init__(self, *texts: str, tokens: tuple[int, int] = (1000, 200)) -> None:
        self.texts = list(texts) or ["Done."]
        self.tokens = tokens
        self.requests: list[dict[str, Any]] = []
        self.keys: list[str] = []
        self.fail: Exception | None = None
        self.messages = self

    def stream(self, **sent: Any) -> Stream:
        self.requests.append(sent)
        if self.fail is not None:
            raise self.fail
        said = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        usage = SimpleNamespace(input_tokens=self.tokens[0], output_tokens=self.tokens[1])
        content = [SimpleNamespace(type="text", text=said)]
        return Stream(SimpleNamespace(content=content, stop_reason="end_turn", model=sent["model"], usage=usage))
