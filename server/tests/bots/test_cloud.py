"""What a bot's `fetch` may reach (ops/bots/fetching.py, cloud.py): https on one of the hosts the bot names, and only
public hosts (named, resolved, never redirected), answering JSON of a bounded size."""

import json
import socket
from types import SimpleNamespace
from typing import Any

import pytest

from glyphh_server.errors import Invalid
from glyphh_server.ops.bots import cloud, fetching
from glyphh_server.ops.bots.agent import run as agent_run


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


async def test_fetch_is_a_get_of_https_json_from_one_of_the_bots_own_hosts(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, dict[str, str], float]] = []

    def fetch(req: Any, timeout: float) -> Any:
        sent.append((req.full_url, dict(req.header_items()), timeout))
        return {"items": [1, 2]}

    monkeypatch.setattr(cloud, "fetch", fetch)
    spec = {"hosts": ["api.example.com", "news.example.org"]}
    assert fetching.fetched(spec, "https://api.example.com/v1/items?n=2") == {"items": [1, 2]}
    assert fetching.fetched(spec, {"url": "https://news.example.org/x", "headers": {"X-Key": 7}}) == {"items": [1, 2]}
    fetching.fetched(spec, {"url": "https://api.example.com/y", "headers": "not headers"})
    assert [(url, timeout) for url, _, timeout in sent] == [
        ("https://api.example.com/v1/items?n=2", cloud.FETCH_SECONDS),
        ("https://news.example.org/x", cloud.FETCH_SECONDS),
        ("https://api.example.com/y", cloud.FETCH_SECONDS),
    ]
    assert sent[0][1] == {"User-agent": fetching.AGENT, "Accept": "application/json"}
    assert sent[1][1]["X-key"] == "7" and sent[1][1]["User-agent"] == fetching.AGENT
    for url in ("http://api.example.com/x", "https://evil.example.net/x", "https://api.example.com.evil.net/x"):
        with pytest.raises(ValueError, match=r"is not https on one of the bot's hosts \(api\.example\.com, news"):
            fetching.fetched(spec, url)
    for none in ({}, {"hosts": "api.example.com"}):
        with pytest.raises(ValueError, match=r"one of the bot's hosts \(none\)"):
            fetching.fetched(none, "https://api.example.com/x")
    for bad in (7, None, {"url": 7}, {"headers": {}}):
        with pytest.raises(ValueError, match="fetch takes a URL"):
            fetching.fetched(spec, bad)
    assert len(sent) == 3  # nothing else was fetched
    bot = SimpleNamespace(spec=spec)
    assert await agent_run.fetch(bot, {"url": "https://api.example.com/z"}) == {"items": [1, 2]}  # off the loop
    assert sent[-1][0] == "https://api.example.com/z"
