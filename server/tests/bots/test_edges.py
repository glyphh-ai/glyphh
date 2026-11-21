"""The bots' edges: Pipedream failing every way it can, a run failing before or while it runs, an answer that came too
late or does not fit, a bot busy with a run, a connection gone since it was scoped, and a run cut off by the server
stopping."""

import asyncio
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.errors import Unavailable
from glyphh_server.ops.bots import props, runs
from glyphh_server.ops.bots.pipedream import Pipedream
from tests.bots.conftest import BOTS, Served, connected, made_bot, serve
from tests.bots.fakes import FakePipedream
from tests.bots.test_runs import answered, started
from tests.db.helpers import person


async def test_pipedream_down_or_unreachable_is_unavailable_and_a_refusal_invalid(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    gmail = await connected(served, ada)
    for mode, status in (("down", 503), ("broken", 503), ("refusing", 422)):
        served.pd.mode = mode
        res = await served.http.delete(f"/v1/connections/{gmail['id']}", headers=ada.headers)
        assert res.status_code == status, (mode, res.text)
    served.pd.mode = ""
    served.pd.accounts = []  # gone at Pipedream already: deleting it here still works
    assert (await served.http.delete(f"/v1/connections/{gmail['id']}", headers=ada.headers)).status_code == 204


async def test_pipedream_off_refuses_before_any_call() -> None:
    pd = Pipedream(httpx.AsyncClient(), Settings(secret_key="x" * 32))
    with pytest.raises(Unavailable):
        await pd.apps(None, None)


def test_an_action_without_an_app_prop_is_run_with_the_callers_values_only() -> None:
    defined = [{"name": "q", "type": "string"}]
    assert props.configured(defined, "apn_1", {"q": "x", "other": 1}) == {"q": "x"}


async def test_a_run_failing_before_its_loop_says_why_and_has_no_gate_to_correct(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    bots = served.app.state.bots

    def no_ada(key: str) -> Any:
        raise RuntimeError("socket closed")

    bots.ada_for = no_ada
    run = await started(served, ada)
    assert (run["status"], run["error"]) == ("failed", "The run failed: RuntimeError: socket closed")
    res = await served.http.post(f"/v1/bot-runs/{run['id']}/wrong", json={"outcome": "skip"}, headers=ada.headers)
    assert res.status_code == 422 and "passed no gate" in res.json()["error"]["message"]

    async def off(bot: Any) -> Any:
        raise Unavailable("Anthropic is off.", reason="anthropic_off")

    bots.claude_of = off
    assert (await started(served, ada))["error"] == "Anthropic is off."


async def test_an_answer_that_does_not_fit_or_comes_too_late_is_refused(
    served: Served, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    run = await answered(served, ada, await started(served, ada), "1=answer 2=skip")
    res = await served.http.post(f"/v1/bot-runs/{run['id']}/answer", json={"answer": "maybe"}, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["options"] == ["yes", "no"]

    async def taken(*_: Any) -> bool:
        return False  # another answer carried it on first

    monkeypatch.setattr(runs, "queue", taken)
    res = await served.http.post(f"/v1/bot-runs/{run['id']}/answer", json={"answer": "yes"}, headers=ada.headers)
    assert res.status_code == 409
    assert (await served.http.get(f"/v1/bot-runs/{uuid.uuid4()}", headers=ada.headers)).status_code == 404


async def test_a_connection_gone_since_it_was_scoped_fails_the_step_that_uses_it(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    bot = await made_bot(served, ada)
    served.pd.accounts = []
    await served.http.post("/v1/connections/sync", headers=ada.headers)
    gone = bot["connections"][0]["connection_id"]
    assert (await served.http.delete(f"/v1/connections/{gone}", headers=ada.headers)).status_code in (204, 404)
    run = await started(served, ada)
    assert run["status"] == "failed" and "gmail-find-email" in run["error"]


async def test_a_bot_with_a_run_going_is_busy_and_a_stopped_server_cuts_the_run_off(engine: AsyncEngine) -> None:
    held = asyncio.Event()

    async def holding(bot: Any) -> Any:
        held.set()
        await asyncio.Event().wait()  # never: the server stops first

    async for s in serve(BOTS, FakePipedream()):
        ada = await person(engine)
        await made_bot(s, ada)
        s.app.state.bots.claude_of = holding
        res = await s.http.post("/v1/bots/inbox-cat/runs", json={"input": "x"}, headers=ada.headers)
        await held.wait()
        busy = await s.http.get("/v1/bots/inbox-cat/gates", headers=ada.headers)
        assert busy.status_code == 409 and "has a run going" in busy.json()["error"]["message"]
    async for s in serve(BOTS, FakePipedream()):
        run = (await s.http.get(f"/v1/bot-runs/{res.json()['id']}", headers=ada.headers)).json()
        assert run["status"] == "failed" and run["error"] == "interrupted by a restart"
