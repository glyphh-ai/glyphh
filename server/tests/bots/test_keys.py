"""The org's own Anthropic key (BYOK): tried with Anthropic before it is kept, shown by its last four characters, its
bots' turns run on it with the markup alone on the meter; without one they run on Glyphh's, let in by the meter (an
allowance spent fails the run saying so), and with neither a run is refused."""

import asyncio
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest
from glyphh.bots import BotError

from glyphh_server.errors import NoBalance, Unavailable
from glyphh_server.llm import meter
from glyphh_server.ops.bots import goes, keys
from tests.bots.agents import play
from tests.bots.conftest import BOTS, SEND, Served, answered, connected, made_bot, ran, serve
from tests.bots.fakes import FakePipedream
from tests.db.helpers import Person

OWN: str = "sk-ant-api03-the-orgs-own-key-1234"
GLYPHHS: str = "sk-ant-glyphh-test-key"
REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}


async def test_an_own_key_is_tried_kept_by_its_last_four_and_its_runs_charge_the_markup_alone(
    served: Served, ana: Person, monkeypatch: pytest.MonkeyPatch
) -> None:
    rates: list[tuple[int, int, int, int]] = []
    real = meter.record

    async def record(engine_: Any, who: Any, model: Any, i: int, o: int) -> int:
        rates.append((model.input_cents_per_mtok, model.output_cents_per_mtok, i, o))
        return await real(engine_, who, model, i, o)

    monkeypatch.setattr(meter, "record", record)
    none = (await served.http.get("/v1/bot-key", headers=ana.headers)).json()
    assert none == {"set": False, "hint": "", "set_at": None, "glyphh_key": True}
    for bad, why in (
        ("not-a-key-at-all-really", "starts sk-ant-"),
        ("sk-ant-api03-a-key-anthropic-says-bad", "not take"),
    ):
        res = await served.http.put("/v1/bot-key", json={"key": bad}, headers=ana.headers)
        assert res.status_code == 422 and why in res.json()["error"]["message"], bad
    for _ in range(2):  # a second time, the key is replaced
        res = await served.http.put("/v1/bot-key", json={"key": f" {OWN} "}, headers=ana.headers)
        assert res.status_code == 200, res.text
    kept = res.json()
    assert (kept["set"], kept["hint"], kept["glyphh_key"]) == (True, "1234", True) and kept["set_at"]
    assert OWN not in res.text
    gmail = await connected(served, ana, allow=False)
    bot = await made_bot(served, ana, connections=[{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}])
    served.agent.script = [play((SEND, REPLY)), play(text="Not sent.")]
    run = await ran(served, ana, bot["slug"], "Reply to Grace")
    assert (run["own_key"], run["input_tokens"], run["status"]) == (True, 1000, "needs_input")
    gone = await served.http.delete("/v1/bot-key", headers=ana.headers)
    assert gone.json()["set"] is False
    done = await answered(served, ana, run["id"], "no")  # carried on after the key went: on Glyphh's now
    assert (done["own_key"], done["input_tokens"], done["status"]) == (False, 2000, "done")
    assert [t.key for t in served.agent.turns] == [OWN, GLYPHHS]
    # Opus: 20% of Anthropic's rate on the org's own key, 120% on Glyphh's; each go's own tokens
    assert rates == [(80, 400, 1000, 200), (480, 2400, 1000, 200)]


async def test_with_no_key_at_all_a_run_is_refused_and_an_own_key_lets_it_run(ana: Person) -> None:
    async for s in serve(BOTS.model_copy(update={"anthropic_api_key": ""}), FakePipedream()):
        bot = await made_bot(s, ana)
        res = await s.http.post(f"/v1/bots/{bot['slug']}/runs", json={}, headers=ana.headers)
        assert res.status_code == 503 and res.json()["error"]["reason"] == "anthropic_off"
        assert "Add your Anthropic API key" in res.json()["error"]["message"]
        assert (await s.http.get(f"/v1/bots/{bot['slug']}/runs", headers=ana.headers)).json()["runs"] == []
        assert (await s.http.get("/v1/bot-key", headers=ana.headers)).json()["glyphh_key"] is False
        with pytest.raises(Unavailable):  # the bot maker's Claude is refused the same way
            await s.app.state.bots.claude_of(SimpleNamespace(org_id=ana.org_id, model="claude-opus-5-5"))
        await s.http.put("/v1/bot-key", json={"key": OWN}, headers=ana.headers)
        run = await ran(s, ana, bot["slug"], "Hi")
        assert (run["status"], run["own_key"]) == ("done", True) and s.agent.turns[0].key == OWN


async def test_an_allowance_spent_fails_the_run_saying_so_before_its_turn(
    served: Served, ana: Person, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def spent(*_: Any) -> Any:
        raise NoBalance("Your plan's tokens this month are used.", reason="tokens")

    bot = await made_bot(served, ana)
    monkeypatch.setattr(meter, "admit", spent)
    run = await ran(served, ana, bot["slug"], "Hi")
    assert run["status"] == "failed" and "tokens this month are used" in run["error"]
    assert run["summary"] == "It failed: Your plan's tokens this month are used."
    assert served.agent.turns == [] and (run["input_tokens"], run["output_tokens"]) == (0, 0)  # no turn was made


async def test_the_bot_makers_claude_is_let_in_by_the_meter_and_its_tokens_charged_after(
    served: Served, ana: Person, monkeypatch: pytest.MonkeyPatch
) -> None:
    recorded: list[tuple[int, int, int]] = []
    real = meter.record

    async def record(engine_: Any, who: Any, model: Any, i: int, o: int) -> int:
        recorded.append((model.input_cents_per_mtok, i, o))
        await real(engine_, who, model, i, o)
        return 42  # as when the allowance is spent and the balance pays

    monkeypatch.setattr(meter, "record", record)
    bot = SimpleNamespace(org_id=ana.org_id, model="claude-opus-5-5")
    claude, own = await served.app.state.bots.claude_of(bot)
    asked = {"prompt": "You draft bots."}
    got = await asyncio.to_thread(claude.answer, "draft", asked, "A bot for my inbox", turns=1)
    assert (got.text, own, claude.charged) == ("Happy to, see you Friday.", False, 42)
    assert recorded == [(480, 1000, 200)] and served.claude.keys == [GLYPHHS]
    assert served.claude.requests[0]["system"] == "You draft bots."

    async def spent(*_: Any) -> Any:
        raise NoBalance("Your plan's tokens this month are used.", reason="tokens")

    monkeypatch.setattr(meter, "admit", spent)
    with pytest.raises(BotError, match="tokens this month are used"):  # said as the meter says it
        await asyncio.to_thread(claude.answer, "draft", asked, "Another")
    assert len(served.claude.requests) == 1 and claude.charged == 42  # Claude was not asked


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
