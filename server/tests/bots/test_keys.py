"""The org's own Anthropic key (BYOK): tried with Anthropic before it is kept, shown by its last four characters, its
bots' agent steps run on it with nothing charged; without one they run on Glyphh's, let in by the meter, and with
neither a run is refused."""

from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import NoBalance, Unavailable
from glyphh_server.ops.bots import goes, keys
from tests.bots.conftest import BOTS, Served, made_bot, serve
from tests.bots.fakes import FakePipedream
from tests.bots.test_runs import answered, started
from tests.db.helpers import person

OWN: str = "sk-ant-api03-the-orgs-own-key-1234"


async def test_an_own_key_is_tried_kept_by_its_last_four_and_its_runs_charge_nothing(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    none = (await served.http.get("/v1/bot-key", headers=ada.headers)).json()
    assert none == {"set": False, "hint": "", "set_at": None, "glyphh_key": True}
    for bad, why in (
        ("not-a-key-at-all-really", "starts sk-ant-"),
        ("sk-ant-api03-a-key-anthropic-says-bad", "not take"),
    ):
        res = await served.http.put("/v1/bot-key", json={"key": bad}, headers=ada.headers)
        assert res.status_code == 422 and why in res.json()["error"]["message"], bad
    for _ in range(2):  # a second time, the key is replaced
        res = await served.http.put("/v1/bot-key", json={"key": f" {OWN} "}, headers=ada.headers)
        assert res.status_code == 200, res.text
    kept = res.json()
    assert (kept["set"], kept["hint"], kept["glyphh_key"]) == (True, "1234", True) and kept["set_at"]
    assert OWN not in res.text
    await made_bot(served, ada)
    run = await answered(served, ada, await started(served, ada), "1=answer 2=skip")
    assert set(served.claude.keys) == {OWN}
    assert (run["own_key"], run["cost_micros"], run["input_tokens"]) == (True, 0, 1000)
    gone = await served.http.delete("/v1/bot-key", headers=ada.headers)
    assert gone.json()["set"] is False


async def test_with_no_key_at_all_a_run_is_refused_and_an_own_key_lets_it_run(engine: AsyncEngine) -> None:
    async for s in serve(BOTS.model_copy(update={"anthropic_api_key": ""}), FakePipedream()):
        ada = await person(engine)
        await made_bot(s, ada)
        res = await s.http.post("/v1/bots/inbox-cat/runs", json={}, headers=ada.headers)
        assert res.status_code == 503 and res.json()["error"]["reason"] == "anthropic_off"
        assert (await s.http.get("/v1/bot-key", headers=ada.headers)).json()["glyphh_key"] is False
        with pytest.raises(Unavailable):  # the key forgotten after the run was let in
            await s.app.state.bots.claude_of(SimpleNamespace(org_id=ada.org_id, model="claude-opus-5-5"))
        await s.http.put("/v1/bot-key", json={"key": OWN}, headers=ada.headers)
        assert (await started(s, ada))["status"] == "needs_input"


async def test_on_glyphhs_key_a_step_the_meter_refuses_fails_the_run_saying_why(
    served: Served, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def spent(*_: Any) -> Any:
        raise NoBalance("Your plan's tokens this month are used.", reason="tokens")

    monkeypatch.setattr(goes.meter, "admit", spent)
    ada = await person(engine)
    await made_bot(served, ada)
    run = await answered(served, ada, await started(served, ada), "1=answer 2=skip")
    assert run["status"] == "failed" and "tokens this month are used" in run["error"]
    assert served.claude.requests == []


def anthropic_answering(status: int) -> type:
    real = anthropic.AsyncAnthropic

    class Client(real):  # type: ignore[misc, valid-type]
        def __init__(self, **kw: Any) -> None:
            body = {"data": [], "has_more": False} if status == 200 else {"error": {}}
            answered = httpx2.MockTransport(lambda _: httpx2.Response(status, json=body))
            kw.setdefault("http_client", httpx2.AsyncClient(transport=answered))  # the SDK copies itself with one
            super().__init__(**kw)

    return Client


async def test_a_key_is_tried_with_anthropic_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    for status, said in ((200, None), (401, "Anthropic does not take that key."), (403, "may not use the Claude API")):
        monkeypatch.setattr(anthropic, "AsyncAnthropic", anthropic_answering(status))
        got = await keys.anthropic_check(OWN)
        assert got == said if said is None else said in str(got)


def test_the_real_ada_and_claude_are_made_with_the_bots_keys() -> None:
    ada = goes._ada("https://ada.test")("glyphh_ak_x")
    assert type(ada).__name__ == "Ada"
    claude = goes._claude(OWN, "claude-haiku-5-5")
    assert type(claude).__name__ == "ApiClaude" and claude.model == "claude-haiku-5-5"
