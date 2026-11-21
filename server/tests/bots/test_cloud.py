"""The cloud's program for a bot: fetch only from public hosts (named, resolved, never redirected, JSON of a bounded
size), and its scoped tools called on the server's loop from the runner's thread."""

import asyncio
import json
import socket
from types import SimpleNamespace
from typing import Any

import pytest

from glyphh_server.errors import Invalid
from glyphh_server.ops.bots import cloud, engine


def test_only_public_host_names_are_hosts_a_bot_may_name() -> None:
    for host in ("api.example.com", "News.Example.com."):
        assert cloud.public_host(host), host
    for host in ("localhost", "10.0.0.1", "[::1]", "intranet", "db.internal", "app.flycast", "me.local"):
        assert not cloud.public_host(host), host
    cloud.check_hosts({"hosts": "not a list"})  # the SDK says what is wrong with that
    with pytest.raises(Invalid) as err:
        cloud.check_hosts({"hosts": ["api.example.com", "169.254.169.254"]})
    assert "169.254.169.254 is not one" in err.value.message


def test_a_host_is_public_only_when_every_address_it_resolves_to_is(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolving(*addresses: str) -> Any:
        def found(*_: Any, **__: Any) -> list[Any]:
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, 443)) for a in addresses]

        return found

    monkeypatch.setattr(socket, "getaddrinfo", resolving("93.184.216.34"))
    assert cloud._resolved_public("example.com")
    monkeypatch.setattr(socket, "getaddrinfo", resolving("93.184.216.34", "10.1.2.3"))
    assert not cloud._resolved_public("example.com")

    def failing(*_: Any, **__: Any) -> Any:
        raise socket.gaierror("no such host")

    monkeypatch.setattr(socket, "getaddrinfo", failing)
    assert not cloud._resolved_public("nowhere.example.com")
    assert cloud.NoRedirect().redirect_request() is None


class Answer:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> "Answer":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def read(self, most: int) -> bytes:
        return self.body[:most]


def test_fetch_answers_json_and_refuses_private_hosts_and_big_answers(monkeypatch: pytest.MonkeyPatch) -> None:
    req = cloud.urllib.request.Request("https://api.example.com/x")
    monkeypatch.setattr(cloud, "_resolved_public", lambda host: False)
    with pytest.raises(ValueError, match="not a public host"):
        cloud.fetch(req, 5)
    monkeypatch.setattr(cloud, "_resolved_public", lambda host: True)
    opened: list[float] = []

    def opener(body: bytes) -> Any:
        def open_(r: Any, timeout: float) -> Answer:
            opened.append(timeout)
            return Answer(body)

        return lambda *handlers: SimpleNamespace(open=open_)

    monkeypatch.setattr(cloud.urllib.request, "build_opener", opener(json.dumps({"ok": 1}).encode()))
    assert cloud.fetch(req, 60) == {"ok": 1} and opened == [cloud.FETCH_SECONDS]
    monkeypatch.setattr(cloud.urllib.request, "build_opener", opener(b"1" * (cloud.FETCH_MAX + 1)))
    with pytest.raises(ValueError, match="more than 5 MB"):
        cloud.fetch(req, 5)


async def test_the_program_fetches_and_calls_its_tools_on_the_servers_loop() -> None:
    asked: list[Any] = []
    ctx = SimpleNamespace(http_json=lambda url, headers=None: asked.append((url, headers)) or {"url": url})

    async def send(given: dict[str, Any]) -> Any:
        return {"sent": given}

    program = cloud.Program({"gmail-send-email": send}, asyncio.get_running_loop())
    assert program.fetch(ctx, "https://a.example.com") == {"url": "https://a.example.com"}
    program.fetch(ctx, {"url": "https://b.example.com", "headers": {"x": "1"}})
    program.fetch(ctx, {"url": "https://c.example.com", "headers": "nope"})
    assert asked[1:] == [("https://b.example.com", {"x": "1"}), ("https://c.example.com", None)]
    with pytest.raises(ValueError, match="takes a URL"):
        program.fetch(ctx, 7)
    tool = program.__getattr__("gmail-send-email")
    assert await asyncio.to_thread(tool, ctx, {"to": "x"}) == {"sent": {"to": "x"}}
    assert await asyncio.to_thread(tool, ctx, "not a dict") == {"sent": {}}
    with pytest.raises(AttributeError):
        program.__getattr__("gmail-delete-everything")
    with pytest.raises(RuntimeError, match="only being checked"):
        cloud.Program({"gmail-send-email": send}).__getattr__("gmail-send-email")(ctx, {})


def test_a_run_whose_steps_left_nothing_has_no_output() -> None:
    bot = SimpleNamespace(spec={"loop": [{"id": "a"}, "not a step"]})
    assert engine.output(bot, SimpleNamespace(data={})) == ""
    assert engine.output(bot, SimpleNamespace(data={"a": "x" * (engine.OUTPUT_MAX + 5)})) == "x" * engine.OUTPUT_MAX
