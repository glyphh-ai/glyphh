"""Bots' gates: per-item gates (one batch of questions a run), each gate's asking policy (ask_below, min_precedents,
audit, shadow, max_questions, default), world-answered gates, ladders, learned approvals and trust, agent output
gates; the hard gates (spend, runs a day, quiet hours, max_items, requires, the kill switch); and what is shown
(`gates`, the report), the demo bot hn_reader included. Ada and `claude` are fakes: no network."""

from __future__ import annotations

import datetime as dt
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List

import pytest

import glyphh.bots.cli as bots_cli
from conftest import FakeAda, FakeClaude, write_bot
from glyphh import cli
from glyphh.bots import Bot, BotError, Claude, Orchestrator, Policy, fill, holds, parse_answers, parse_expr, validate
from glyphh.bots.rules import ExprError, json_answer, quiet

REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "examples" / "bots"

ITEM_SPEC = {
    "name": "worth",
    "layers": [{"name": "i", "segments": [{"name": "s", "roles": [
        {"name": "title", "text_encoding": "bag_of_words"},
        {"name": "score", "numeric_config": {"min_value": 0, "max_value": 100, "bin_width": 10}},
        {"name": "id", "key_part": True, "similarity_weight": 0},
    ]}]}],
    "output": {"costs": {"drop": {"keep": 2}, "keep": {"drop": 1}}, "ask_below": 0.7},
}
YESNO_SPEC = {**ITEM_SPEC, "name": "ok", "output": {"ask_below": 0.7}}
ROUTE_SPEC = {**ITEM_SPEC, "name": "route", "output": {"ask_below": 0.6}}

PROGRAM = '''
import json


def fetch(ctx, inputs):
    return ctx.http_json("https://api.example.com/items")


def item_case(ctx, item):
    return {"i": {"s": {"title": item["title"], "score": item["score"], "id": str(item["id"])}}}


def ok_case(ctx, data):
    return {"i": {"s": {"title": "deliver", "score": len((data.get("worth") or {}).get("keep") or []), "id": ctx.run_id}}}


def deliver(ctx, inputs):
    out = ctx.dir / "out"
    out.mkdir(exist_ok=True)
    (out / "kept.json").write_text(json.dumps(inputs))
    return {"kept": len(inputs or [])}


def spend(ctx, inputs):
    return {"left": ctx.spend(inputs, "an api")}


def remember_cases(ctx, inputs):
    g = ctx.gate("worth")
    calls = [g.decide(item_case(ctx, it), item=it["id"]) for it in ctx.data["fetch"]["items"]]
    return {"calls": [c.to_dict() for c in calls]}


def attempt(ctx, rung, item):
    ctx.spend(0.1, "attempt " + rung)
    return {"rung": rung, "id": item["id"]}


def worked(ctx, rung, result, item):
    return rung in item.get("works", [])


def answer_ok(ctx, answer, data):
    return True if answer.get("summary", "").startswith("ok") else "the summary must start with ok"
'''


def items(*scores: int, works: Any = None) -> Dict[str, Any]:
    found = []
    for i, s in enumerate(scores, 1):
        it: Dict[str, Any] = {"id": i, "title": f"story {i}", "score": s}
        if works is not None:
            it["works"] = works[i - 1]
        found.append(it)
    return {"items": found}


def gate(**policy: Any) -> Dict[str, Any]:
    return {"case": "item_case", "outcomes": ["keep", "drop"], "question": "Keep it?", "spec": ITEM_SPEC, **policy}


def items_spec(loop: Any = None, gates: Any = None, **over: Any) -> Dict[str, Any]:
    spec: Dict[str, Any] = {
        "slug": "lister",
        "name": "Lister",
        "summary": "Keeps the items worth keeping",
        "agent": "agent.md",
        "touches": "read_only",
        "hosts": ["api.example.com"],
        "gates": gates or {"worth": gate()},
        "loop": loop or [
            {"id": "fetch", "run": "fetch"},
            {"id": "worth", "gate": "worth", "each": "$fetch.items", "label": "title", "key": "id",
             "on": {"empty:keep": "end"}},
            {"id": "deliver", "run": "deliver", "input": "$worth.keep"},
        ],
        "limits": {"seconds": 60},
    }
    spec.update(over)
    return spec


class World:
    def __init__(self, answer: Any) -> None:
        self.answer, self.notified = answer, []

    def fetch(self, req: Any, timeout: float) -> Any:
        return self.answer(req.full_url) if callable(self.answer) else self.answer

    def notify(self, title: str, text: str) -> None:
        self.notified.append((title, text))


@pytest.fixture
def world() -> World:
    return World(items(80, 20, 55))


@pytest.fixture
def orch(fake_ada: FakeAda, fake_claude: FakeClaude, bots_home: Path, world: World) -> Orchestrator:
    return Orchestrator(fake_ada, root=bots_home, claude=Claude(run=fake_claude), fetch=world.fetch,
                        notify=world.notify, today=lambda: dt.date(2026, 11, 3),
                        now=lambda: dt.datetime(2026, 11, 3, 9, 0))


def install(orch: Orchestrator, tmp_path: Path, spec: Dict[str, Any], name: str = "a") -> Any:
    orch.install(write_bot(tmp_path / name / spec["slug"], spec, PROGRAM))
    return orch.runner(spec["slug"])


def by_score(threshold: int, p: float = 0.9):
    return lambda case: ("keep", p) if case["i"]["s"]["score"] >= threshold else ("drop", p)


def problems(folder: Path) -> str:
    with pytest.raises(BotError) as e:
        Bot.load(folder)
    return " | ".join(e.value.problems or [e.value.message])


# the rules: paths, requires, schemas, quiet hours, a batch's answers


def test_fill_reads_paths_into_earlier_data():
    data = {"a": {"items": [{"t": "x"}], "n": 2}, "b": "text"}
    assert fill("$a.items", data) == [{"t": "x"}] and fill("$a.items.0.t", data) == "x"
    assert fill("$a.nope", data) is None and fill("$c.items", data) is None
    assert fill("n=$a.n, b=$b.", data) == 'n=2, b="text".' and fill("$c here", data) == "$c here"


def test_requires_is_a_small_safe_language():
    data = {"s": {"items": [1, 2, 3], "name": "it's", "ok": True, "none": None}}
    for text, want in [
        ("len($s.items) > 2", True), ("len($s.items) == 3 and $s.ok", True), ("not $s.ok or 1 >= 2", False),
        ("$s.name == \"it's\"", True), ("$s.name != 'x'", True), ("($s.none == null) and len($s.missing) == 0", True),
        ("$s.none > 3", False), ("-1.5 < 0", True), ("$s.items", True), ("false or true and false", False),
    ]:
        assert holds(text, data) is want, text
    for bad in ("", "len(", "1 +", "import os", "$s.items ==", "(1", "1 2", "'open"):
        with pytest.raises(ExprError):
            parse_expr(bad)


def test_an_answers_schema_and_json():
    schema = {"type": "object", "required": ["summary", "picks"], "additionalProperties": False, "properties": {
        "summary": {"type": "string", "minLength": 3, "maxLength": 50, "pattern": "^ok"},
        "picks": {"type": "array", "minItems": 1, "maxItems": 2, "items": {"type": "integer", "minimum": 1, "maximum": 9}},
        "tone": {"enum": ["plain", "warm"]}, "n": {"anyOf": [{"type": "null"}, {"const": 3}]}}}
    assert validate({"summary": "ok fine", "picks": [1], "tone": "plain", "n": None}, schema) == []
    bad = validate({"summary": "no", "picks": [0, 1, 2], "x": 1, "tone": "loud", "n": 4}, schema)
    for said in ("$.summary is shorter", "does not match", "more than 2 items", "$.picks[0] is under 1",
                 "$.x is not allowed", "$.tone is not one of", "$.n fits none"):
        assert any(said in b for b in bad), said
    assert validate("x", {"type": ["number", "null"]}) == ["$ is not number or null"]
    assert validate(12, {"type": "number", "maximum": 10}) == ["$ is over 10"]
    assert validate("toolong", {"maxLength": 3}) == ["$ is longer than 3"]
    assert validate([], {"minItems": 1}) == ["$ has fewer than 1 items"] and validate({}, {"required": ["a"]})
    assert validate({"a": "x"}, {"additionalProperties": {"type": "number"}}) == ["$.a is not number"]
    assert json_answer('```json\n{"a": 1}\n```') == {"a": 1} and json_answer('Sure: {"a": 2} done') == {"a": 2}
    assert json_answer("[1, 2]") == [1, 2] and json_answer("so: [3] ok") == [3]
    with pytest.raises(ValueError):
        json_answer("no json here")


def test_quiet_hours_wrap_midnight():
    at = lambda h, m=0: dt.datetime(2026, 11, 3, h, m)  # noqa: E731
    assert quiet("22:00-07:00", at(23)) and quiet("22:00-07:00", at(6, 59)) and not quiet("22:00-07:00", at(7))
    assert quiet("12:00-13:30", at(13, 29)) and not quiet("12:00-13:30", at(14))
    with pytest.raises(ValueError):
        quiet("late", at(1))


def test_a_batchs_answers_every_way_they_are_given():
    nums, opts = [1, 2, 3], ["read", "skip"]
    want = {1: "read", 2: "skip", 3: "skip"}
    assert parse_answers("1=read 2=skip 3=skip", nums, opts) == want
    assert parse_answers(["1=READ", "rest=skip"], nums, opts) == want
    assert parse_answers('{"1": "read", "2": "skip", "3": "skip"}', nums, opts) == want
    assert parse_answers({1: "read", "all": "skip"}, nums, opts) == want
    assert parse_answers("1=read,2=skip;3=skip", nums, opts) == want and parse_answers("read", [4], opts) == {4: "read"}
    for bad, said in (("1=read", "not answered"), ("1=maybe rest=skip", "not one of"), ("9=read rest=skip", "not one of the items"),
                      ("read", "answer each as"), ("{nope", "not JSON")):
        with pytest.raises(ValueError, match=said):
            parse_answers(bad, nums, opts)


# a package's gates and limits are checked when it loads


def test_malformed_gates_and_limits_are_refused_at_load(tmp_path):
    spec = items_spec(
        gates={"worth": gate(ask_below=2, min_precedents=-1, audit="lots", shadow="yes", max_questions=1.5, default="maybe",
                             world=True),
               "ok": {"case": "ok_case", "outcomes": ["sure", "nope"], "spec": YESNO_SPEC},
               "decisions": {"case": "ok_case", "outcomes": ["decisions", "x"], "spec": YESNO_SPEC}},
        loop=[
            {"id": "fetch", "run": "fetch", "requires": "len($later) > 1"},
            {"id": "worth", "gate": "worth", "each": "fetch.items", "on": {"maybe:keep": "nowhere", "else:x": "end"},
             "label": 3, "max_items": 0},
            {"id": "pick", "run": "fetch", "each": "$fetch.items", "requires": "len(", "otherwise": "later"},
            {"id": "later", "run": "deliver", "approval": "deliver", "approval_gate": "ok", "touches": "pays"},
            {"id": "out", "run": "deliver", "approval_gate": "ghost", "touches": "sends"},
            {"id": "climb", "ladder": "ok", "start": "up", "on_fail": "cry"},
            {"id": "noladder", "ladder": "ghost"},
            {"id": "say", "agent": "x", "schema": {"type": "thing", "format": "email", "properties": {"a": []}}, "check": ""},
            {"id": "w2", "gate": "worth", "each": "$nothing.items", "on": "x"},
        ],
        limits={"seconds": 0, "usd_per_run": "lots", "usd_per_day": -1, "quiet_hours": "late", "runs_per_day": 1.5,
                "max_items": True, "speed": 3},
    )
    found = problems(write_bot(tmp_path / "bad", spec))
    for said in (
        "ask_below must be a number from 0 to 1", "min_precedents must be a whole number", "audit must be a number",
        "shadow must be true or false", "max_questions must be a whole number", "default must be one of",
        "a world-answered gate has no audit or shadow", "outcomes may not be named decisions",
        "requires reads $later, not an earlier step", "each must be $id.path", "on maybe:keep is not a rule",
        "on else:x is not a rule", "on maybe:keep goes to nowhere", "label must be a path", "max_items must be a positive",
        "each is for a gate or a ladder", "requires does not parse", "otherwise must be skip or end",
        "it touches pays, more than the bot's read_only", "approval_gate ok's outcomes must be yes and no",
        "an approval_gate needs the step's approval", "approval_gate ghost is not one of the gates",
        "start must be one of ok's rungs", "a ladder needs try", "a ladder needs check", "on_fail must be one of",
        "no gate ghost in gates for its ladder", "type thing is not one of", "format is not a keyword",
        "schema.a must be an object", "check must name", "each reads $nothing.items, not an earlier step",
        "on must map rules", "limits must be positive whole numbers: seconds", "limits must be positive dollars: usd_per_run",
        "positive dollars: usd_per_day", 'quiet_hours as "HH:MM-HH:MM"', "whole numbers: runs_per_day",
        "whole numbers: max_items", "speed is not one",
    ):
        assert said in found, said


def test_an_outward_step_needs_its_approval_and_functions_must_exist(tmp_path):
    spec = items_spec(touches="sends", loop=[
        {"id": "fetch", "run": "fetch", "approval": "fetch"},
        {"id": "send", "run": "deliver", "touches": "sends"},
        {"id": "climb", "ladder": "worth", "try": "nope", "check": "neither"},
        {"id": "say", "agent": "x", "check": "ghost"},
    ])
    found = problems(write_bot(tmp_path / "out", spec))
    for said in ("step send: it touches sends but has no approval", "program.py has no function nope",
                 "program.py has no function neither", "program.py has no function ghost"):
        assert said in found, said
    assert check_limits_message() == "limits must be an object"


def check_limits_message() -> str:
    from glyphh.bots.package import check_limits

    return check_limits([])[0].split(" (")[0]


# per-item gates


def test_a_per_item_gate_asks_once_for_the_unsure_items_and_learns_from_every_answer(orch, tmp_path, fake_ada, world):
    runner = install(orch, tmp_path, items_spec())
    model = "bot-lister-gate-worth"
    first = runner.run(routine=True)
    assert first.status == "needs_input" and first.options == ["keep", "drop"]
    assert [b["n"] for b in first.batch] == [1, 2, 3] and first.batch[0]["label"] == "story 1"
    assert "3 to answer" in first.question and "no precedents yet" in first.question
    assert first.answer_with == "glyphh bot continue lister 1=keep 2=drop rest=drop"
    assert world.notified == [("Lister", "needs_input at worth: glyphh bot continue lister")]
    with pytest.raises(BotError, match="waits for answers to 3 items"):
        runner.resume()
    with pytest.raises(BotError, match="not answered"):
        runner.resume("1=keep")
    done = runner.resume(["1=keep", "2=drop", "3=keep"])
    assert done.status == "done" and done.run_id == first.run_id
    out = done.data["worth"]
    assert [i["id"] for i in out["keep"]] == [1, 3] and [i["id"] for i in out["drop"]] == [2]
    assert out["asked"] == 3 and out["decided"] == 0 and {d["by"] for d in out["decisions"]} == {"person"}
    assert fake_ada.outcomes(model) == ["keep", "drop", "keep"]
    assert fake_ada.cases[model][0][0] == {"i": {"s": {"title": "story 1", "score": 80, "id": "1"}}}
    assert json.loads((runner.bot.dir / "out" / "kept.json").read_text())[0]["title"] == "story 1"
    assert done.data["_gates"]["worth"]["outcome"] == "keep 2, drop 1"
    assert orch.record_of("lister")["ask_pct"] == 100

    fake_ada.rule[model] = lambda case: ("keep", 0.95) if case["i"]["s"]["score"] >= 50 else ("drop", 0.55)
    world.answer = items(90, 30, 10)
    asked: List[str] = []
    orch.ask = lambda q, o: asked.append(q) or "drop"
    second = orch.runner("lister").run()
    assert second.status == "done" and len(asked) == 2 and "[1/2] story 2" in asked[0] and "[2/2] story 3" in asked[1]
    assert "Ada's guess is drop (P 0.55), not sure enough" in asked[0]
    d = second.data["worth"]["decisions"]
    assert [(x["n"], x["outcome"], x["by"]) for x in d] == [(1, "keep", "ada"), (2, "drop", "person"), (3, "drop", "person")]
    assert d[1]["agreed"] is True and fake_ada.outcomes(model)[-2:] == ["drop", "drop"]
    assert orch.record_of("lister")["ask_pct"] == round(100 * 5 / 6)


def test_on_routes_after_the_loop_and_nothing_kept_ends_the_run(orch, tmp_path, fake_ada, world):
    runner = install(orch, tmp_path, items_spec())
    fake_ada.cases["bot-lister-gate-worth"].append(({}, "drop"))
    fake_ada.sure["bot-lister-gate-worth"] = "drop"
    ended = runner.run()
    assert ended.status == "done" and ended.reason == "gate worth: keep 0, drop 3; the run ends here"
    assert not (runner.bot.dir / "out").exists()
    for rules, want in (({"all:drop": "end"}, "end"), ({"any:keep": "end", "else": "deliver"}, "deliver")):
        assert type(runner)._route_each({"on": rules}, ended.data["worth"]) == want
    assert type(runner)._route_each({"on": {"any:keep": "end"}}, ended.data["worth"]) is None


def test_max_questions_defaults_the_rest_or_holds_them_for_the_next_run(orch, tmp_path, fake_ada, world):
    world.answer = items(1, 2, 3, 4)
    spec = items_spec(gates={"worth": gate(max_questions=2, default="drop")})
    runner = install(orch, tmp_path, spec)
    orch.ask = lambda q, o: "keep"
    got = orch.runner("lister").run().data["worth"]
    assert [(d["n"], d["by"], d["outcome"]) for d in got["decisions"]] == [
        (1, "person", "keep"), (2, "person", "keep"), (3, "default", "drop"), (4, "default", "drop")]
    assert got["defaulted"] == 2 and fake_ada.outcomes("bot-lister-gate-worth") == ["keep", "keep"]

    spec = items_spec(slug="holder", gates={"worth": gate(max_questions=2)})
    install(orch, tmp_path, spec, "b")
    first = orch.runner("holder").run().data["worth"]
    assert first["deferred"] == 2 and [d["by"] for d in first["decisions"]][2:] == ["deferred", "deferred"]
    world.answer = items(9)
    world.answer["items"][0]["id"] = 9
    second = orch.runner("holder").run().data["worth"]
    assert [d["key"] for d in second["decisions"]] == ["3", "4", "9"] and second["deferred"] == 1
    assert [d["by"] for d in second["decisions"]] == ["person", "person", "deferred"]


def test_max_items_is_a_hard_cap(orch, tmp_path, fake_ada, world):
    world.answer = items(*range(10))
    spec = items_spec(limits={"max_items": 4})
    install(orch, tmp_path, spec)
    orch.ask = lambda q, o: "drop"
    got = orch.runner("lister").run()
    assert len(got.data["worth"]["decisions"]) == 4 and got.data["worth"]["dropped"] == 6
    assert any("max_items 4, 6 items dropped" in line for line in got.log)


def test_an_each_that_is_not_a_list_fails_the_run(orch, tmp_path, world):
    world.answer = {"items": "nope"}
    runner = install(orch, tmp_path, items_spec())
    assert runner.run().reason == "worth: each $fetch.items is not a list"


# the asking policy


def test_ask_below_and_min_precedents_decide_when_ada_may_decide_alone(orch, tmp_path, fake_ada, world):
    model = "bot-lister-gate-worth"
    runner = install(orch, tmp_path, items_spec(gates={"worth": gate(ask_below=0.6, min_precedents=3)}))
    assert fake_ada.specs[model]["output"]["ask_below"] == 0.6
    fake_ada.rule[model] = by_score(50, p=0.65)
    fake_ada.cases[model] += [({}, "keep"), ({}, "drop")]
    orch.ask = lambda q, o: "drop"
    asked = orch.runner("lister").run().data["worth"]["decisions"]
    assert {d["mode"] for d in asked} == {"few"} and all(d["by"] == "person" for d in asked)
    decided = orch.runner("lister").run().data["worth"]["decisions"]
    assert [(d["outcome"], d["by"]) for d in decided] == [("keep", "ada"), ("drop", "ada"), ("keep", "ada")]
    policy = Policy.of("g", gate(ask_below=0.9))
    call = policy.judge(type("D", (), {"outcome": "keep", "probabilities": {"keep": 0.8}, "ask": False})(), 5, "s")
    assert call.ask and call.mode == "unsure" and call.guess == "keep" and not call.sure
    nothing = policy.judge(type("D", (), {"outcome": "other", "probabilities": {}, "ask": False})(), 5, "s")
    assert nothing.ask and nothing.outcome is None


def test_an_audit_asks_some_sure_calls_and_records_agreement_or_overrule(orch, tmp_path, fake_ada, world):
    model = "bot-lister-gate-worth"
    runner = install(orch, tmp_path, items_spec(gates={"worth": gate(audit=1.0)}))
    fake_ada.cases[model].append(({}, "keep"))
    fake_ada.rule[model] = by_score(50)
    orch.ask = lambda q, o: "keep"
    got = orch.runner("lister").run().data["worth"]["decisions"]
    assert {d["mode"] for d in got} == {"audit"} and [d["agreed"] for d in got] == [True, False, True]
    stats = runner.gates()["gates"]["worth"]
    assert stats["audit"] == {"asked": 3, "agreed": 2, "rate": 0.667} and stats["overrules"]["audit"] == 1
    assert stats["decisions"]["person"] == 3 and fake_ada.outcomes(model)[-3:] == ["keep", "keep", "keep"]
    some = Policy.of("g", gate(audit=0.3))
    share = sum(some.judge(type("D", (), {"outcome": "keep", "probabilities": {"keep": 0.99}, "ask": False})(), 9,
                           f"run:{i}").mode == "audit" for i in range(400)) / 400
    assert 0.2 < share < 0.4


def test_shadow_always_asks_and_measures_agreement(orch, tmp_path, fake_ada, world):
    model = "bot-lister-gate-worth"
    runner = install(orch, tmp_path, items_spec(gates={"worth": gate(shadow=True)}))
    fake_ada.cases[model].append(({}, "keep"))
    fake_ada.rule[model] = by_score(50)
    orch.ask = lambda q, o: "drop"
    asked = orch.runner("lister").run().data["worth"]["decisions"]
    assert [d["mode"] for d in asked] == ["shadow"] * 3 and [d["agreed"] for d in asked] == [False, True, False]
    assert runner.gates()["gates"]["worth"]["shadow"] == {"asked": 3, "agreed": 1, "rate": 0.333}


def test_a_single_gates_policy_default_and_question_budget(orch, tmp_path, fake_ada, world):
    loop = [{"id": "fetch", "run": "fetch"}, {"id": "ok", "gate": "ok", "on": {"yes": "end", "no": "end"}}]
    gates = {"ok": {"case": "ok_case", "outcomes": ["yes", "no"], "spec": YESNO_SPEC, "max_questions": 0, "default": "no"}}
    install(orch, tmp_path, items_spec(loop=loop, gates=gates))
    got = orch.runner("lister").run()
    assert got.reason == "gate ok said no: the run ends here" and got.data["_gates"]["ok"]["by"] == "default"
    assert fake_ada.outcomes("bot-lister-gate-ok") == []
    del gates["ok"]["default"]
    install(orch, tmp_path, items_spec(loop=loop, gates=gates), "b")
    assert "no questions left this run" in orch.runner("lister").run().reason


# world-answered gates


def test_a_world_answered_gate_keeps_the_case_until_the_world_says(orch, tmp_path, fake_ada, world):
    model = "bot-lister-gate-worth"
    runner = install(orch, tmp_path, items_spec(gates={"worth": gate(world=True)}))
    orch.ask = lambda q, o: "keep"
    run = orch.runner("lister").run()
    assert fake_ada.outcomes(model) == [] and run.data["worth"]["asked"] == 3
    assert runner.gates()["gates"]["worth"]["world"] == {"recorded": 0, "waiting": 3}
    said = runner.outcome(run.run_id, "worth", "2", "drop")
    assert said["item"] == "2" and said["decided"] == "keep" and not said["overruled"]
    assert fake_ada.outcomes(model) == ["drop"]
    fake_ada.rule[model] = by_score(0)
    sure = orch.runner("lister").run()
    assert sure.data["worth"]["decided"] == 3
    hit = runner.outcome("last", "worth", "3", "drop")
    assert hit["overruled"] and hit["run"] == sure.run_id
    stats = runner.gates()["gates"]["worth"]
    assert stats["overrules"]["world"] == 1 and stats["world"]["recorded"] == 2
    for args, said in ((("nope", "worth", "1", "keep"), "has no case"), ((run.run_id, "ghost", None, "keep"), "no gate ghost"),
                       ((run.run_id, "worth", "1", "maybe"), "not one of"), ((run.run_id, "worth", None, "keep"), "say which item"),
                       (("zzz", "worth", None, "keep"), "has no case")):
        with pytest.raises(BotError, match=said):
            runner.outcome(*args)


def test_a_batch_waiting_is_answered_one_by_one_at_a_terminal_and_a_single_world_gate_waits(orch, tmp_path, fake_ada):
    install(orch, tmp_path, items_spec())
    orch.runner("lister").run(routine=True)
    said = iter(["keep", "drop", "keep"])
    orch.ask = lambda q, o: next(said)
    done = orch.runner("lister").resume()
    assert [d["outcome"] for d in done.data["worth"]["decisions"]] == ["keep", "drop", "keep"]

    loop = [{"id": "fetch", "run": "fetch"}, {"id": "ok", "gate": "ok", "on": {"yes": "end", "no": "end"}}]
    gates = {"ok": {"case": "ok_case", "outcomes": ["yes", "no"], "spec": YESNO_SPEC, "world": True}}
    orch.ask = None
    runner = install(orch, tmp_path, items_spec(loop=loop, gates=gates), "b")
    waiting = runner.run()
    assert runner.resume(["yes"]).reason == "gate ok said yes: the run ends here"
    assert fake_ada.outcomes("bot-lister-gate-ok") == []
    assert runner.outcome(waiting.run_id, "ok", None, "no")["outcome"] == "no"
    assert fake_ada.outcomes("bot-lister-gate-ok") == ["no"]


def test_a_programs_own_gate_calls_and_outcomes(orch, tmp_path, fake_ada, world):
    loop = [{"id": "fetch", "run": "fetch"}, {"id": "calls", "run": "remember_cases"}]
    runner = install(orch, tmp_path, items_spec(loop=loop, gates={"worth": gate(world=True)}))
    model = "bot-lister-gate-worth"
    first = runner.run()
    assert [c["mode"] for c in first.data["calls"]["calls"]] == ["new"] * 3
    from glyphh.bots.runner import Ctx

    ctx = Ctx(runner, first.run_id, [])
    g = ctx.gate("worth")
    assert g.record_outcome("keep", item=1)["outcome"] == "keep" and fake_ada.outcomes(model) == ["keep"]
    g.record({"i": {"s": {"title": "x", "score": 1, "id": "x"}}}, "drop")
    with pytest.raises(ValueError, match="not one of"):
        g.record({}, "maybe")
    assert g.info().precedents == 2 and g.policy.world
    fake_ada.sure[model] = "keep"
    assert ctx.gate("worth").decide({"i": {}}).sure


# ladders


def test_a_ladder_climbs_from_the_cheapest_it_predicts_and_learns_what_it_took(orch, tmp_path, fake_ada, world):
    world.answer = items(10, 90, works=[["small", "mid", "big"], ["big"]])
    gates = {"route": {"case": "item_case", "outcomes": ["small", "mid", "big"], "spec": ROUTE_SPEC, "default": "mid"}}
    loop = [{"id": "fetch", "run": "fetch"},
            {"id": "do", "ladder": "route", "each": "$fetch.items", "label": "title", "key": "id", "try": "attempt",
             "check": "worked"}]
    runner = install(orch, tmp_path, items_spec(loop=loop, gates=gates))
    model = "bot-lister-gate-route"
    got = runner.run().data["do"]
    assert [(i["start"], i["rung"], i["by"]) for i in got["items"]] == [("mid", "mid", "default"), ("mid", "big", "default")]
    assert got["items"][1]["tried"] == [{"rung": "mid", "ok": False}, {"rung": "big", "ok": True}]
    assert fake_ada.outcomes(model) == ["mid", "big"] and runner.store.spent(run=got and runner.store.recent(1)[0]["id"]) == pytest.approx(0.3)
    fake_ada.rule[model] = lambda case: ("small", 0.9) if case["i"]["s"]["score"] < 50 else ("big", 0.9)
    again = runner.run().data["do"]["items"]
    assert [(i["start"], i["rung"], i["by"]) for i in again] == [("small", "small", "ada"), ("big", "big", "ada")]
    stats = runner.gates()["gates"]["route"]["ladder"]
    assert stats == {"runs": 4, "worked": 4, "escalated": 1, "took": {"mid": 1, "big": 2, "small": 1}}

    world.answer = {"items": [{"id": 1, "title": "hard", "score": 50, "works": []}]}
    single = [{"id": "fetch", "run": "fetch"},
              {"id": "do", "ladder": "route", "input": "$fetch.items.0", "try": "attempt", "check": "worked", "on_fail": "end"},
              {"id": "deliver", "run": "deliver"}]
    install(orch, tmp_path, items_spec(loop=single, gates=gates), "b")
    del fake_ada.rule[model]
    ended = orch.runner("lister").run()
    assert ended.status == "done" and "no rung of route worked (mid, big)" in ended.reason
    single[1]["on_fail"] = "fail"
    install(orch, tmp_path, items_spec(loop=single, gates=gates), "c")
    assert orch.runner("lister").run().status == "failed"
    single[1]["on_fail"] = "next"
    install(orch, tmp_path, items_spec(loop=single, gates=gates), "d")
    carried = orch.runner("lister").run()
    assert carried.status == "done" and carried.data["do"]["ok"] is False and carried.data["deliver"] == {"kept": 0}


def test_the_coder_example_climbs_its_ladder_with_fake_trials(orch, fake_ada, monkeypatch, tmp_path):
    import sqlite3
    import sys

    orch.install(EXAMPLES / "lab")
    orch.install(EXAMPLES / "coder")
    trials = sys.modules["trials"]
    need = {"h1_slugify": "haiku", "h2_ratelimit": "opus"}
    ran: List[str] = []

    def trial(exp: str, task: Dict[str, Any], strategy: str, model: str) -> Dict[str, Any]:
        ran.append(f"{task['id']}:{model}")
        order = ["haiku", "sonnet", "opus"]
        return {"pass": order.index(model) >= order.index(need.get(task["id"], "sonnet")), "cost": 0.25}

    monkeypatch.setattr(trials, "trial", trial)
    monkeypatch.setattr(trials, "ledger", lambda: sqlite3.connect(str(tmp_path / "ledger.sqlite")).__enter__())
    trials.ledger().execute("CREATE TABLE IF NOT EXISTS trials (exp TEXT, task TEXT, kind TEXT, strategy TEXT, model TEXT,"
                            " pass INT, cost REAL, seconds REAL, turns INT, note TEXT, at REAL)")
    got = orch.runner("coder").run()
    assert got.status == "done", got.reason
    work = {i["label"]: (i["start"], i["rung"]) for i in got.data["work"]["items"]}
    assert work["h1_slugify"] == ("sonnet", "sonnet") and work["h2_ratelimit"] == ("sonnet", "opus")
    assert "h2_ratelimit:sonnet" in ran and "h2_ratelimit:opus" in ran
    assert fake_ada.outcomes("bot-coder-gate-route").count("opus") == 1
    assert orch.runner("coder").store.spent(run=got.run_id) == pytest.approx(0.25 * len(ran))


# approvals, learned, under trust


def approval_spec(touches: str = "sends", step_touches: Any = None, gate_name: Any = "ok") -> Dict[str, Any]:
    step: Dict[str, Any] = {"id": "deliver", "run": "deliver", "input": "$fetch.items", "approval": "deliver the list"}
    if gate_name:
        step["approval_gate"] = gate_name
    if step_touches:
        step["touches"] = step_touches
    gates = {"ok": {"case": "ok_case", "outcomes": ["yes", "no"], "spec": YESNO_SPEC}}
    return items_spec(touches=touches, gates=gates, loop=[{"id": "fetch", "run": "fetch"}, step])


def test_a_learned_approval_asks_until_the_gate_is_sure_and_trust_allows(orch, tmp_path, fake_ada, world):
    model = "bot-lister-gate-ok"
    runner = install(orch, tmp_path, approval_spec())
    first = runner.run(routine=True)
    assert first.status == "needs_input" and first.options == ["yes", "no"] and "no precedents yet" in first.question
    assert runner.resume("yes").status == "done" and fake_ada.outcomes(model) == ["yes"]
    fake_ada.sure[model] = "yes"
    orch.ask = lambda q, o: "yes"
    asked = orch.runner("lister").run()
    assert any("approval deliver the list: yes (the person's)" in line for line in asked.log)
    assert fake_ada.outcomes(model) == ["yes", "yes"]
    orch.verdict("lister", "trust", "autonomous")
    orch.ask = None
    alone = orch.runner("lister").run()
    assert alone.status == "done" and any("by its approval gate ok (P 0.95), trust autonomous" in line for line in alone.log)
    fake_ada.sure[model] = "no"
    refused = orch.runner("lister").run()
    assert refused.reason == "approval gate ok said no to deliver the list"
    del fake_ada.sure[model]
    waits = orch.runner("lister").run()
    assert waits.status == "needs_input" and "Ada's guess is" in waits.question
    assert orch.runner("lister").resume("no").reason == "the person said no to deliver the list"
    rows = [r for r in runner.store.decisions(gate="ok") if r["by"] == "person"]
    assert rows[-1]["outcome"] == "no" and runner.gates()["gates"]["ok"]["decisions"]["ada"] == 2


def test_trust_ask_outward_asks_only_outward_steps_and_pays_never_go_alone(orch, tmp_path, fake_ada, world):
    install(orch, tmp_path, approval_spec(step_touches="drafts", gate_name=None))
    orch.verdict("lister", "trust", "ask_outward")
    assert orch.runner("lister").run().status == "done"
    orch.verdict("lister", "trust", "ask_all")
    assert orch.runner("lister").run().status == "needs_input"

    install(orch, tmp_path, approval_spec(gate_name=None), "b")
    orch.verdict("lister", "trust", "ask_outward")
    assert orch.runner("lister").run().status == "needs_input"
    orch.runner("lister").resume("no")
    orch.verdict("lister", "trust", "autonomous")
    assert orch.runner("lister").run().status == "done"

    install(orch, tmp_path, approval_spec(touches="pays", gate_name=None), "c")
    assert orch.runner("lister").run().status == "needs_input"
    orch.runner("lister").resume("no")
    install(orch, tmp_path, approval_spec(touches="pays"), "d")
    fake_ada.cases["bot-lister-gate-ok"].append(({}, "yes"))
    fake_ada.sure["bot-lister-gate-ok"] = "yes"
    assert orch.runner("lister").run().status == "done"
    orch.verdict("lister", "trust", "ask_outward")
    assert orch.runner("lister").run().status == "needs_input"


# agent output gates


def test_an_agents_answer_is_held_to_its_schema_and_check_with_one_retry(orch, tmp_path, fake_claude):
    schema = {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}
    loop = [{"id": "say", "agent": "Sum it up", "schema": schema, "check": "answer_ok"}, {"id": "deliver", "run": "deliver", "input": "$say.summary"}]
    runner = install(orch, tmp_path, items_spec(loop=loop, gates={}))
    fake_claude.answers = ["not json", '```json\n{"summary": "ok, all fine"}\n```']
    got = runner.run()
    assert got.status == "done" and got.data["say"] == {"summary": "ok, all fine"}
    assert "fitting this JSON Schema" in fake_claude.calls[0][0][-1] and "it is not JSON" in fake_claude.calls[1][0][-1]
    fake_claude.answers = ['{"summary": "meh"}', '{"summary": 3}']
    bad = runner.run()
    assert bad.status == "failed" and "still not right: $.summary is not string" in bad.reason
    assert "the summary must start with ok" in fake_claude.calls[-1][0][-1]


# hard gates: spend, runs a day, quiet hours, requires, the kill switch


def test_spend_limits_end_the_run_before_a_step_would_pass_them(orch, tmp_path, fake_claude):
    loop = [{"id": "one", "agent": "first"}, {"id": "two", "agent": "second"}, {"id": "deliver", "run": "deliver"}]
    runner = install(orch, tmp_path, items_spec(loop=loop, gates={}, limits={"usd_per_run": 0.5, "usd_per_day": 0.9}))
    fake_claude.cost = 0.3
    first = runner.run()
    assert first.status == "done" and "spend: $0.30 of usd_per_run $0.50 spent; two (about $0.30) would pass it" in first.reason
    assert len(fake_claude.calls) == 1 and "deliver" not in first.data
    assert "usd_per_run" in runner.run().reason and len(fake_claude.calls) == 2
    assert "usd_per_run" in runner.run().reason and len(fake_claude.calls) == 3
    fourth = runner.run()
    assert "spend: $0.90 of usd_per_day $0.90 spent: the run ends here" in fourth.reason and len(fake_claude.calls) == 3

    loop = [{"id": "pay", "run": "spend", "input": 0.4}, {"id": "again", "run": "spend", "input": 0.2},
            {"id": "deliver", "run": "deliver"}]
    other = install(orch, tmp_path, items_spec(slug="payer", loop=loop, gates={}, limits={"usd_per_run": 0.5}), "b")
    got = other.run()
    assert got.data["pay"] == {"left": pytest.approx(0.1)} and got.data["again"] == {"left": 0.0}
    assert "spend: $0.60 of usd_per_run $0.50 spent: the run ends here" in got.reason
    free = install(orch, tmp_path, items_spec(slug="free", loop=loop, gates={}), "c")
    assert free.run().data["pay"] == {"left": None}


def test_runs_a_day_and_quiet_hours_skip_runs(orch, tmp_path):
    loop = [{"id": "deliver", "run": "deliver"}]
    runner = install(orch, tmp_path, items_spec(loop=loop, gates={}, limits={"runs_per_day": 2, "quiet_hours": "22:00-07:00"}))
    assert runner.run().status == "done" and runner.run(routine=True).status == "done"
    third = runner.run()
    assert third.status == "skipped" and "2 runs today already" in third.reason and third.to_dict()["status"] == "skipped"
    night = orch.runner("lister")
    night.now = lambda: dt.datetime(2026, 11, 3, 23, 30)
    night.today = lambda: dt.date(2026, 11, 4)
    assert night.run(routine=True).reason == "quiet hours (22:00-07:00): the routine run waits"
    assert night.run().status == "done"


def test_requires_skips_a_step_or_ends_the_run(orch, tmp_path, world):
    loop = [{"id": "fetch", "run": "fetch"},
            {"id": "deliver", "run": "deliver", "input": "$fetch.items", "requires": "len($fetch.items) > 5"},
            {"id": "last", "run": "deliver", "requires": "$fetch.items.0.score >= 80 and $deliver == null",
             "otherwise": "end"}]
    runner = install(orch, tmp_path, items_spec(loop=loop, gates={}))
    got = runner.run()
    assert got.data["deliver"] is None and got.data["last"] == {"kept": 0}
    assert any("skip deliver: it requires len($fetch.items) > 5" in line for line in got.log)
    world.answer = items(10)
    ended = runner.run()
    assert ended.status == "done" and ended.reason.startswith("last requires") and "last" not in ended.data


def test_a_paused_bot_refuses_to_run_until_resumed(orch, tmp_path):
    runner = install(orch, tmp_path, items_spec())
    runner.run(routine=True)
    assert runner.pause("too noisy")["paused"]
    with pytest.raises(BotError, match="paused .*too noisy"):
        runner.run(routine=True)
    with pytest.raises(BotError, match="paused"):
        runner.resume("1=keep rest=drop")
    assert "too noisy" in runner.status()["paused"] and "too noisy" in orch.status()["bots"][0]["paused"]
    assert runner.unpause()["paused"] is False and runner.resume("1=keep rest=drop").status == "done"


# corrections, the gates' record, the report


def test_wrong_corrects_one_item_of_a_per_item_gate(orch, tmp_path, fake_ada):
    runner = install(orch, tmp_path, items_spec())
    orch.ask = lambda q, o: "keep"
    run = orch.runner("lister").run()
    with pytest.raises(BotError, match="say which"):
        runner.wrong(run.run_id, "drop")
    fixed = runner.wrong("last", "drop", item="2")
    assert fixed["said"] == "keep" and fixed["now"] == "drop" and fixed["item"] == "2"
    assert fake_ada.outcomes("bot-lister-gate-worth")[-1] == "drop"
    assert runner.gates()["gates"]["worth"]["overrules"]["wrong"] == 1 and orch.record_of("lister")["overruled_pct"] == 100


def test_gates_and_the_report_show_the_ask_rate_falling(orch, tmp_path, fake_ada, world):
    runner = install(orch, tmp_path, items_spec())
    model = "bot-lister-gate-worth"
    orch.ask = lambda q, o: "keep"
    orch.runner("lister").run()
    fake_ada.rule[model] = lambda case: ("keep", 0.95) if case["i"]["s"]["score"] >= 50 else ("drop", 0.5)
    orch.runner("lister").run()
    fake_ada.rule[model] = by_score(50)
    orch.runner("lister").run()
    stats = runner.gates(10)
    g = stats["gates"]["worth"]
    assert stats["runs"] == 3 and [r["rate"] for r in g["ask_rate_by_run"]] == [1.0, 0.333, 0.0]
    assert g["precedents"] == 4 and g["decisions"] == {"ada": 5, "person": 4, "default": 0, "total": 9}
    assert g["ask_rate"] == 0.444 and g["agreement"] == {"asked": 1, "agreed": 0, "rate": 0.0}

    made = runner.report()
    page = Path(made["report"]).read_text()
    assert made["report"] == str(runner.bot.dir / "report.html") and made["ask_rate"] == {"first": 1.0, "last": 0.0, "runs": 3}
    assert "<svg" in page and "100% → 0%" in page and "story 1" in page and "times it asked you" in page
    assert '<div class="n">4</div>' in page and '<div class="n">5</div>' in page and 'href="out/kept.json"' in page
    assert "<script" not in page and "http" not in page.split("<body>")[1].replace("glyphh", "")
    for colour in re.findall(r"(?<![-\w])color:\s*(#[0-9a-fA-F]{6})", page):
        r, gg, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
        assert 0.2126 * r + 0.7152 * gg + 0.0722 * b >= 0x99, colour


def test_a_report_with_no_runs_says_so(orch, tmp_path):
    runner = install(orch, tmp_path, items_spec())
    page = Path(runner.report()["report"]).read_text()
    assert "No run yet." in page and "No run has passed a gate yet." in page


# the demo bot: hn_reader


HITS = {"hits": [
    {"objectID": "101", "title": "Show HN: A tiny Lisp in 200 lines", "url": "https://www.example.org/lisp", "points": 320,
     "num_comments": 80, "created_at_i": 0, "author": "a"},
    {"objectID": "102", "title": "Ask HN: What are you reading?", "points": 40, "num_comments": 300, "created_at_i": 0},
    {"objectID": "103", "title": "Celebrity buys a yacht", "url": "https://news.example.com/yacht", "points": 15,
     "num_comments": 2, "created_at_i": 0},
    {"objectID": "", "title": "broken"},
]}


def test_hn_reader_asks_about_the_unsure_stories_writes_a_checked_digest_and_reports(orch, fake_ada, fake_claude, world):
    seen: List[str] = []

    def answer(url: str) -> Any:
        seen.append(url)
        return HITS if "front_page" in url else {"hits": []}

    world.answer = answer
    orch.install(EXAMPLES / "hn_reader")
    runner = orch.runner("hn_reader")
    first = runner.run(routine=True)
    assert seen[0] == "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=50"
    assert "numericFilters=points%3E%3D100%2Ccreated_at_i%3E%3D" in seen[1]
    assert first.status == "needs_input" and [b["label"] for b in first.batch][0] == "Show HN: A tiny Lisp in 200 lines"
    case = fake_ada.specs["bot-hn-reader-gate-worth"]
    assert case["output"]["ask_below"] == 0.75
    story = first.data["stories"]["items"][0]
    assert (story["domain"], story["kind"], story["hn"]) == ("example.org", "show", "https://news.ycombinator.com/item?id=101")
    assert first.data["stories"]["items"][1]["kind"] == "ask"

    fake_claude.answers = ["# Hacker News\n- [Lisp](https://www.example.org/lisp)",
                           "# Hacker News\n- [Lisp](https://www.example.org/lisp)\n- [Ask](https://news.ycombinator.com/item?id=102)"]
    done = runner.resume("1=read 2=read 3=skip")
    assert done.status == "done", done.reason
    assert "the digest leaves out 1 of the stories: Ask HN" in fake_claude.calls[1][0][-1]
    digest = (runner.bot.dir / "out" / "digest.md").read_text()
    assert "item?id=102" in digest and done.data["deliver"]["stories"] == 2
    assert fake_ada.outcomes("bot-hn-reader-gate-worth") == ["read", "read", "skip"]
    again = runner.run(routine=True)
    assert again.reason == "the program ended the run: no story the bot has not judged before"
    page = Path(runner.report()["report"]).read_text()
    assert "HN reader" in page and "Show HN: A tiny Lisp" in page and "out/digest.md" in page


def test_a_run_waiting_from_3_8_carries_on(orch, bot_folder, fake_ada):
    orch.install(bot_folder)
    runner = orch.runner("digest")
    case = {"d": {"s": {"new": 1, "run": "old"}}}
    runner.store.save("old", "needs_input", 1, {"fetch": {"items": [{"title": "x"}]}},
                      {"gate": "worth", "case": case, "question": "Worth it?", "options": ["send", "skip"]}, "Worth it?", [])
    assert runner.resume("skip").reason == "gate worth said skip: the run ends here"
    assert fake_ada.cases["bot-digest-gate-worth"] == [(case, "skip")]
    runner.store.save("older", "needs_input", 3, {"write": "text"},
                      {"approval": "deliver", "question": "deliver?", "options": ["yes", "no"]}, "deliver?", [])
    assert runner.resume("no").reason == "the person said no to send the digest"


# the command


@pytest.fixture
def glyphh_bot(monkeypatch, fake_ada: FakeAda, fake_claude: FakeClaude, bots_home: Path, capsys, world: World):
    monkeypatch.setattr(bots_cli, "connect", lambda root: fake_ada)
    monkeypatch.setattr(bots_cli, "Claude", lambda: Claude(run=fake_claude))
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    monkeypatch.setattr("glyphh.bots.runner._urlopen", world.fetch)

    def run(*argv: str, code: int = 0) -> Any:
        got = cli.main(["bot", *argv, "-q"])
        out = capsys.readouterr()
        assert got == code, out.err
        return json.loads(out.out if code == 0 or out.out else out.err)

    return run


def test_the_gate_commands(glyphh_bot, tmp_path, fake_ada):
    folder = write_bot(tmp_path / "src" / "lister", items_spec(gates={"worth": gate(world=True)}), PROGRAM)
    glyphh_bot("install", str(folder))
    asked = glyphh_bot("run", "lister")
    assert asked["status"] == "needs_input" and len(asked["batch"]) == 3 and asked["answer_with"].startswith("glyphh bot continue")
    err = glyphh_bot("continue", "lister", "1=keep", code=1)
    assert "not answered" in err["error"]["message"]
    done = glyphh_bot("continue", "lister", "1=keep", "2=drop", "rest=keep")
    assert done["status"] == "done" and len(done["data"]["worth"]["keep"]) == 2
    got = glyphh_bot("outcome", "lister", "last", "worth", "2", "keep")
    assert got["outcome"] == "keep" and fake_ada.outcomes("bot-lister-gate-worth") == ["keep"]
    assert "say which item" in glyphh_bot("outcome", "lister", "last", "worth", "keep", code=1)["error"]["message"]
    assert "at most two" in glyphh_bot("outcome", "lister", "last", "worth", "1", "2", "keep", code=1)["error"]["message"]
    fixed = glyphh_bot("wrong", "lister", "last", "keep", "--item", "1")
    assert fixed["now"] == "keep" and fixed["item"] == "1"
    gates = glyphh_bot("gates", "lister", "--runs", "5")
    assert gates["gates"]["worth"]["decisions"]["person"] == 3 and gates["gates"]["worth"]["world"]["recorded"] == 1
    report = glyphh_bot("report", "lister")
    assert Path(report["report"]).exists()
    assert glyphh_bot("pause", "lister", "--why", "on holiday")["why"] == "on holiday"
    assert "paused" in glyphh_bot("run", "lister", "--routine", code=1)["error"]["message"]
    assert glyphh_bot("resume", "lister")["paused"] is False
    assert glyphh_bot("run", "lister", "--routine")["status"] == "needs_input"
    assert glyphh_bot("continue", "lister", '{"1": "keep", "rest": "drop"}')["status"] == "done"
