"""Bots anywhere: a host may give a bot its program (Glyphh's cloud gives connections' actions, never code of the
bot's own), a gate's case may be its fields instead of a function, and an agent step may run over the Claude API on
the person's own Anthropic key (ApiClaude), its tokens counted. Ada and Claude are fakes: no network."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from conftest import FakeAda, write_bot
from glyphh.bots import ApiClaude, Bot, BotError, Claude, Runner, from_env, priced
from glyphh.bots.claude import DEFAULT_MODEL

ITEM_SPEC = {
    "name": "worth",
    "layers": [{"name": "i", "segments": [{"name": "s", "roles": [
        {"name": "title", "text_encoding": "bag_of_words"},
        {"name": "id", "key_part": True, "similarity_weight": 0},
    ]}]}],
    "output": {"ask_below": 0.7},
}


def spec() -> Dict[str, Any]:
    return {
        "slug": "lister",
        "name": "Lister",
        "agent": "agent.md",
        "touches": "read_only",
        "gates": {"worth": {"case": {"i": {"s": {"title": "$item.title", "id": "$item.id"}}},
                            "outcomes": ["keep", "drop"], "question": "Keep it?", "spec": ITEM_SPEC}},
        "loop": [
            {"id": "fetch", "run": "inbox"},
            {"id": "worth", "gate": "worth", "each": "$fetch.items", "label": "title", "key": "id",
             "on": {"empty:keep": "end"}},
            {"id": "sum", "agent": "Sum up: $worth.keep", "skill": "digest"},
        ],
    }


class Host:
    """What a host gives a bot in place of program.py."""

    def __init__(self) -> None:
        self.calls: List[Any] = []

    def inbox(self, ctx: Any, inputs: Any) -> Any:
        self.calls.append(inputs)
        return {"items": [{"id": 1, "title": "one"}, {"id": 2, "title": "two"}]}


class Stream:
    def __init__(self, message: Any) -> None:
        self.message = message

    def __enter__(self) -> "Stream":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def get_final_message(self) -> Any:
        return self.message


class FakeApi:
    """anthropic.Anthropic, faked: `messages.stream` keeps what it was asked and answers `reply`."""

    def __init__(self, text: str = "the sum", stop: str = "end_turn", model: str = "claude-sonnet-5-5") -> None:
        self.asked: List[Dict[str, Any]] = []
        self.fail: Exception | None = None
        self.reply = SimpleNamespace(
            content=[SimpleNamespace(type="thinking", thinking="..."), SimpleNamespace(type="text", text=f" {text} ")],
            stop_reason=stop, model=model, usage=SimpleNamespace(input_tokens=1200, output_tokens=300),
        )
        self.messages = self

    def stream(self, **kw: Any) -> Stream:
        self.asked.append(kw)
        if self.fail:
            raise self.fail
        return Stream(self.reply)


def test_a_host_gives_the_program_and_a_gate_case_is_its_fields(tmp_path):
    folder = write_bot(tmp_path / "lister", spec(), program="raise RuntimeError('never imported')\n")
    host = Host()
    bot = Bot.load(folder, program=host)
    assert bot.program is host
    ada, api = FakeAda(), FakeApi()
    runner = Runner(bot, ada, claude=ApiClaude(client=api), ask=lambda q, o: "keep")
    runner.install()
    done = runner.run()
    assert done.status == "done" and host.calls == [None]
    assert ada.cases["bot-lister-gate-worth"][0] == ({"i": {"s": {"title": "one", "id": 1}}}, "keep")
    assert done.data["sum"] == "the sum"
    assert runner.tokens == {"input_tokens": 1200, "output_tokens": 300}
    asked = api.asked[0]
    assert asked["model"] == "claude-sonnet-5-5" and asked["thinking"] == {"type": "adaptive"}
    assert asked["system"].startswith("You are Digest.") and asked["timeout"] == 300.0
    assert asked["messages"][0]["content"].startswith("Sum up: [") and "One line per item." in asked["messages"][0]["content"]


def test_a_hosts_program_must_have_every_function_and_a_case_must_be_a_name_or_fields(tmp_path):
    folder = write_bot(tmp_path / "lister", spec())
    with pytest.raises(BotError) as e:
        Bot.load(folder, program=SimpleNamespace())
    assert e.value.problems == ["step fetch: program.py has no function inbox"]
    bad = spec()
    bad["gates"]["worth"]["case"] = {}
    with pytest.raises(BotError) as e:
        Bot.load(write_bot(tmp_path / "bad", bad), program=Host())
    assert "case must name the program.py function that builds its case, or be its fields" in e.value.problems[0]


def test_fill_fills_inside_objects_and_lists():
    from glyphh.bots import fill

    data = {"a": {"to": "x@y.z", "n": 2}}
    assert fill({"to": "$a.to", "cc": ["$a.to", "n=$a.n"], "k": 3}, data) == {"to": "x@y.z", "cc": ["x@y.z", "n=2"], "k": 3}


def test_a_single_gates_fields_read_the_runs_data(tmp_path):
    one = spec()
    one["gates"]["worth"]["case"] = {"i": {"s": {"title": "$fetch.items", "id": "run"}}}
    one["loop"] = [{"id": "fetch", "run": "inbox"}, {"id": "worth", "gate": "worth", "on": {"keep": "end", "drop": "end"}}]
    ada = FakeAda()
    runner = Runner(Bot.load(write_bot(tmp_path / "one", one), program=Host()), ada, claude=ApiClaude(client=FakeApi()),
                    ask=lambda q, o: "drop")
    runner.install()
    assert runner.run().status == "done"
    case, outcome = ada.cases["bot-lister-gate-worth"][0]
    assert outcome == "drop" and case["i"]["s"]["id"] == "run" and case["i"]["s"]["title"][0]["title"] == "one"


def test_a_run_is_given_its_input_and_no_step_may_be_called_input(tmp_path):
    given = spec()
    given["loop"] = [{"id": "worth", "gate": "worth", "each": "$input.items", "label": "title", "key": "id",
                      "on": {"empty:keep": "end"}}]
    ada = FakeAda()
    runner = Runner(Bot.load(write_bot(tmp_path / "g", given), program=Host()), ada, claude=ApiClaude(client=FakeApi()),
                    ask=lambda q, o: "keep")
    runner.install()
    done = runner.run(given={"items": [{"id": 7, "title": "seven"}]})
    assert done.status == "done" and done.data["input"]["items"][0]["id"] == 7
    assert ada.cases["bot-lister-gate-worth"][0][0] == {"i": {"s": {"title": "seven", "id": 7}}}
    named = spec()
    named["loop"][0]["id"] = "input"
    with pytest.raises(BotError) as e:
        Bot.load(write_bot(tmp_path / "n", named), program=Host())
    assert "no step may be called input: $input is what the run is given" in e.value.problems


def test_api_claude_counts_its_cost_and_says_what_failed():
    api = FakeApi(model="claude-opus-5-5")
    claude = ApiClaude(client=api, model="haiku")
    assert claude.model == "claude-haiku-5-5"
    got = claude.answer("a", {"prompt": "be brief"}, "hi", seconds=30)
    assert (got.text, got.input_tokens, got.output_tokens) == ("the sum", 1200, 300)
    assert got.cost_usd == pytest.approx((1200 * 4 + 300 * 20) / 1e6)
    assert api.asked[0]["model"] == "claude-haiku-5-5"
    assert claude.agent("a", {"prompt": "", "model": "opus"}, "hi") == "the sum" and api.asked[1]["model"] == "claude-opus-5-5"
    assert priced("someone-else", 1_000_000, 0) == 4.0
    api.fail = RuntimeError("invalid x-api-key")
    with pytest.raises(BotError, match="Claude failed: RuntimeError: invalid x-api-key"):
        claude.answer("a", {}, "hi")
    with pytest.raises(BotError, match="declined"):
        ApiClaude(client=FakeApi(stop="refusal")).answer("a", {}, "hi")
    with pytest.raises(BotError, match="needs Claude Code"):
        claude.build("make", Path("."))


def test_api_claude_needs_a_key_and_the_anthropic_package(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(BotError, match="no Anthropic API key"):
        ApiClaude()
    made: List[Dict[str, Any]] = []
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda **kw: made.append(kw) or "client"))
    assert ApiClaude(api_key="sk-test").client == "client" and made == [{"api_key": "sk-test", "max_retries": 3}]
    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(BotError, match="pip install 'glyphh\\[api\\]'"):
        ApiClaude(api_key="sk-test")


def test_the_bot_command_uses_the_api_when_rrotor_says(monkeypatch):
    monkeypatch.delenv("GLYPHH_BOT_CLAUDE", raising=False)
    assert isinstance(from_env(), Claude)
    monkeypatch.setenv("GLYPHH_BOT_CLAUDE", "api")
    monkeypatch.setenv("GLYPHH_BOT_MODEL", "sonnet")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(Anthropic=lambda **kw: "client"))
    got = from_env()
    assert isinstance(got, ApiClaude) and got.model == "claude-sonnet-5-5"
    monkeypatch.delenv("GLYPHH_BOT_MODEL")
    assert from_env().model == DEFAULT_MODEL


def test_claude_p_reports_its_tokens(fake_claude):
    import subprocess

    def run(argv: List[str], **kw: Any) -> Any:
        said = {"result": "ok", "usage": {"input_tokens": 7, "output_tokens": 3, "cache_read_input_tokens": "x"}}
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(said), stderr="")

    got = Claude(run=run).answer("a", {}, "hi")
    assert (got.input_tokens, got.output_tokens) == (7, 3)
    assert Claude(run=fake_claude).answer("a", {}, "hi").input_tokens == 0
