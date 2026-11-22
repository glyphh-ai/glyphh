"""ops/projects/repo.py and claude.py: a project's repo through GitHub's REST API (GitHub faked at the HTTP layer),
and Claude's Messages API with tools (the anthropic client faked)."""

import base64
import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest

from glyphh_server.errors import Unavailable
from glyphh_server.ops.projects.claude import Claude
from glyphh_server.ops.projects.repo import Repo

API: str = "https://api.github.com/repos/acme/site"


class GitHub:
    """GitHub's answers by method and path; every request kept."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, str, Any]] = []
        self.said: dict[tuple[str, str], tuple[int, Any]] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = str(request.url)[len(API) :]
        self.asked.append((request.method, path, json.loads(request.content) if request.content else None))
        assert request.headers["authorization"] == "Bearer t-1"
        if path == "/down":
            raise httpx.ConnectError("no route")
        status, body = self.said.get((request.method, path), (404, {"message": "Not Found"}))
        return httpx.Response(status, text=body) if isinstance(body, str) else httpx.Response(status, json=body)


async def test_a_repo_is_read_through_githubs_api() -> None:
    hub = GitHub()
    text = base64.b64encode(b"# Site\n").decode()
    hub.said |= {
        ("GET", "/git/ref/heads/release/1.2"): (200, {"object": {"sha": "abc"}}),
        ("GET", "/git/trees/abc?recursive=1"): (
            200,
            {
                "tree": [
                    {"path": "src", "type": "tree"},
                    {"path": "src/b.py", "type": "blob"},
                    {"path": "a.md", "type": "blob"},
                ]
            },
        ),
        ("GET", "/contents/docs/a%20b.md?ref=abc"): (200, {"encoding": "base64", "content": text}),
        ("GET", "/contents/src?ref=abc"): (200, [{"name": "b.py"}]),
        ("GET", "/contents/logo.png?ref=abc"): (
            200,
            {"encoding": "base64", "content": base64.b64encode(b"\xff\xfe").decode()},
        ),
        ("GET", "/contents/odd?ref=abc"): (500, "not json"),
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(hub)) as http:
        repo = Repo(http, "t-1", "acme/site")
        assert await repo.head("release/1.2") == "abc"
        assert await repo.tree("abc") == ["a.md", "src/b.py"]
        assert await repo.read("docs/a b.md", "abc") == "# Site\n" and await repo.read("gone.md", "abc") is None
        for path, why in (("src", "a folder, or too big"), ("logo.png", "is not text"), ("odd", r"\(500\)")):
            with pytest.raises(Unavailable, match=why):
                await repo.read(path, "abc")
        with pytest.raises(Unavailable, match=r"GitHub did not find the branch nope \(404\): Not Found"):
            await repo.head("nope")
        with pytest.raises(Unavailable, match="GitHub did not answer"):
            await repo._ask("GET", "/down")


async def test_a_turns_changes_are_one_commit_and_a_pull_request() -> None:
    hub = GitHub()
    hub.said |= {
        ("POST", "/git/refs"): (201, {}),
        ("POST", "/git/trees"): (201, {"sha": "t1"}),
        ("POST", "/git/commits"): (201, {"sha": "c1"}),
        ("PATCH", "/git/refs/heads/turn-1-ada-k3x9"): (200, {}),
        ("POST", "/pulls"): (201, {"html_url": "https://github.com/acme/site/pull/4", "number": 4}),
        ("PUT", "/pulls/4/merge"): (200, {"merged": True, "sha": "m1"}),
        ("PUT", "/pulls/5/merge"): (405, {"message": "Pull Request is not mergeable"}),
        ("PUT", "/pulls/6/merge"): (409, "conflict"),
        ("PUT", "/pulls/7/merge"): (500, {"message": "Server Error"}),
        ("PATCH", "/pulls/4"): (200, {}),
    }
    async with httpx.AsyncClient(transport=httpx.MockTransport(hub)) as http:
        repo = Repo(http, "t-1", "acme/site")
        await repo.branch("turn-1-ada-k3x9", "abc")
        made = await repo.commit("turn-1-ada-k3x9", "abc", {"b.md": None, "a.md": "hi"}, "Ada: hi", "Ada")
        assert made == "c1"
        assert await repo.open("turn-1-ada-k3x9", "main", "Ada: hi", "I said hi.") == {
            "url": "https://github.com/acme/site/pull/4",
            "number": 4,
        }
        assert await repo.merge(4, "Merge PR #4") == (True, "m1")
        assert await repo.merge(5, "x") == (False, "Pull Request is not mergeable")
        assert await repo.merge(6, "x") == (False, "not mergeable")
        with pytest.raises(Unavailable, match=r"did not merge the pull request \(500\): Server Error"):
            await repo.merge(7, "x")
        await repo.close(4)
        await repo.drop("turn-1-ada-k3x9")  # gone already is fine
        with pytest.raises(Unavailable, match=r"did not close the pull request \(404\)"):
            await repo.close(9)
    sent = {(m, p): b for m, p, b in hub.asked}
    assert sent[("POST", "/git/refs")] == {"ref": "refs/heads/turn-1-ada-k3x9", "sha": "abc"}
    assert sent[("POST", "/git/trees")] == {
        "base_tree": "abc",
        "tree": [
            {"path": "a.md", "mode": "100644", "type": "blob", "content": "hi"},
            {"path": "b.md", "mode": "100644", "type": "blob", "sha": None},
        ],
    }
    assert sent[("POST", "/git/commits")] == {
        "message": "Ada: hi",
        "tree": "t1",
        "parents": ["abc"],
        "author": {"name": "Ada", "email": "bots@glyphh.ai"},
    }
    assert sent[("PATCH", "/git/refs/heads/turn-1-ada-k3x9")] == {"sha": "c1"}
    assert ("DELETE", "/git/refs/heads/turn-1-ada-k3x9", None) in hub.asked


async def test_claude_is_asked_with_the_steps_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[dict[str, Any]] = []

    class Messages:
        async def create(self, **given: Any) -> Any:
            asked.append(given)
            if given["system"] == "fail":
                raise anthropic.APIError("overloaded", httpx.Request("POST", "https://api.anthropic.com"), body=None)
            return SimpleNamespace(content=[], usage=SimpleNamespace(input_tokens=1, output_tokens=1))

    def client(**given: Any) -> Any:
        assert given == {"api_key": "sk-ant-x", "max_retries": 2}
        return SimpleNamespace(messages=Messages())

    monkeypatch.setattr(anthropic, "AsyncAnthropic", client)
    claude = Claude("sk-ant-x", "claude-opus-5-5")
    tools = [{"name": "read_file"}]
    assert (await claude.create("You are Ada.", [{"role": "user", "content": "Go"}], tools)).usage.input_tokens == 1
    assert asked[0] == {
        "model": "claude-opus-5-5",
        "max_tokens": 16_000,
        "system": "You are Ada.",
        "messages": [{"role": "user", "content": "Go"}],
        "tools": tools,
    }
    await claude.create("You are Ada.", [], tools, "low")  # a run's effort goes with the request, when it has one
    assert asked[1]["output_config"] == {"effort": "low"} and "output_config" not in asked[0]
    with pytest.raises(Unavailable, match="Claude did not answer: overloaded"):
        await claude.create("fail", [], tools)
