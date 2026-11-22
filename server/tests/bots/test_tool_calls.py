"""A bot on a rrotor calls its tools on the server (POST /v1/bots/runs/{id}/tool, bearer its run's tool token):
a connection's tool run as the org, `fetch` from one of its hosts; any other tool, host or token refused, and the
token good only while its run is out on the rrotor."""

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Unavailable
from glyphh_server.ops.bots import cloud, remote_in, tool_calls
from tests.bots.conftest import made_bot
from tests.bots.remote import OnRrotor, online, result, rrotor_fixture  # noqa: F401 (the fixture)
from tests.db.helpers import person
from tests.link import Rt


async def _out(r: OnRrotor, engine: AsyncEngine, **over: Any) -> tuple[Any, Rt, str, str]:
    ada = await person(engine)
    rt = await online(engine, ada)
    await made_bot(r.s, ada, runs_on=str(rt.id), **over)
    run = (await r.s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)).json()
    return ada, rt, run["id"], r.hub.last().inputs["tool_token"]


async def _call(r: OnRrotor, run_id: str, token: str | None, tool: str, given: Any = None) -> Any:
    headers = {"authorization": f"Bearer {token}"} if token else {}
    res = await r.s.http.post(f"/v1/bots/runs/{run_id}/tool", json={"tool": tool, "input": given}, headers=headers)
    return res.status_code, res.json()


async def test_a_bots_tools_answer_its_run_on_the_rrotor(
    on_rrotor: OnRrotor, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    ada, rt, run_id, token = await _out(on_rrotor, engine)
    status, got = await _call(on_rrotor, run_id, token, "gmail-find-email", {"q": "lunch"})
    assert status == 200 and "result" in got, got
    assert on_rrotor.s.pd.runs[-1]["id"] == "gmail-find-email"
    assert (await _call(on_rrotor, run_id, token, "slack-send"))[1] == {
        "error": "slack-send is neither fetch nor a tool the bot may use (scope it on a connection)"
    }
    _, said = await _call(on_rrotor, run_id, token, "fetch", "https://api.example.com/x")
    assert said["error"].startswith("https://api.example.com/x is not https on one of the bot's hosts (none)")

    async def stuck(*_: Any) -> Any:
        raise TimeoutError

    async def down(*_: Any) -> Any:
        raise Unavailable("Pipedream is down.")

    async def broken(*_: Any) -> Any:
        raise RuntimeError("boom")

    for fake, error in ((stuck, "took longer than 120 seconds"), (down, "Pipedream is down."), (broken, "boom")):
        monkeypatch.setattr(tool_calls, "_ran", fake)
        assert error in (await _call(on_rrotor, run_id, token, "gmail-find-email"))[1]["error"]
    monkeypatch.undo()
    await on_rrotor.landed(rt, ada, uuid.UUID(run_id), result())
    assert (await _call(on_rrotor, run_id, token, "gmail-find-email"))[1] == {"error": tool_calls.NOT_OUT}


async def test_fetch_gets_json_from_one_of_the_bots_hosts(
    on_rrotor: OnRrotor, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    fetched: list[Any] = []

    def fake(req: Any, timeout: float) -> Any:
        fetched.append((req.full_url, req.headers))
        return {"weather": "sun"}

    monkeypatch.setattr(cloud, "fetch", fake)
    spec = {
        "hosts": ["api.example.com"],
        "loop": [{"id": "page", "run": "fetch", "input": "https://api.example.com/x"}],
    }
    _, _, run_id, token = await _out(on_rrotor, engine, spec=spec)
    assert (await _call(on_rrotor, run_id, token, "fetch", "https://api.example.com/x"))[1] == {
        "result": {"weather": "sun"}
    }
    given = {"url": "https://api.example.com/y", "headers": {"X-Key": "k"}}
    assert (await _call(on_rrotor, run_id, token, "fetch", given))[1] == {"result": {"weather": "sun"}}
    assert fetched[-1][0] == "https://api.example.com/y" and fetched[-1][1]["X-key"] == "k"
    for bad in ("http://api.example.com/x", "https://other.example.com/x"):
        assert (
            "is not https on one of the bot's hosts (api.example.com)"
            in (await _call(on_rrotor, run_id, token, "fetch", bad))[1]["error"]
        )
    assert (await _call(on_rrotor, run_id, token, "fetch", 3))[1]["error"].startswith("fetch takes a URL")


async def test_only_the_runs_own_token_opens_it(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    _, _, run_id, token = await _out(on_rrotor, engine)
    assert (await _call(on_rrotor, run_id, None, "fetch"))[0] == 401
    assert (await _call(on_rrotor, run_id, "not-a-token", "fetch"))[0] == 401
    assert (await _call(on_rrotor, str(uuid.uuid4()), token, "fetch"))[0] == 401  # another run's
    secret = on_rrotor.s.app.state.bots.settings.secret_key
    other = remote_in.signed.sign(secret, {"k": "other", "run": run_id, "org": str(uuid.uuid4())}, 60)
    assert (await _call(on_rrotor, run_id, other, "fetch"))[0] == 401
