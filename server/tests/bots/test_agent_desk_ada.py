"""Ada as a bot's tools (ops/bots/agent/desk.py, deciding.py; docs/specs/bot-agent-loop.md, 4): `decide` answers
Ada's outcome for each item and whether it is sure, keeping what it is sure of; `ask_person` asks the person, about a
decision's items (their answers learned by its Ada model and kept as decisions) or anything the bot needs to know."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from glyphh.bots.runner import RunStore

from glyphh_server.ops.bots import probe
from glyphh_server.ops.bots.agent import deciding
from glyphh_server.ops.bots.agent.turn import ERROR, Outcome
from tests.bots.agents import play
from tests.bots.conftest import DECIDE, WORTH_SPEC, Served, answered, inbox, made_bot, ran
from tests.bots.fakes import MAIL, FakeAda
from tests.db.helpers import Person

ASK: str = "ask_person"
ITEMS: dict[str, Any] = {"decision": "worth", "items": MAIL}
GATE: str = "bot-inbox-cat-gate-worth"
BAD: str = "Give a decision's name and its items, each an object (at most 200 at once)."


def sure(s: Served, rule: Any) -> None:
    s.ada.cases[GATE].append(({}, "skip"))  # Ada decides alone once it holds a precedent
    s.ada.rule[GATE] = rule


async def listed(s: Served, who: Person, slug: str) -> list[dict[str, Any]]:
    res = await s.http.get(f"/v1/bots/{slug}/decisions", headers=who.headers)
    return list(res.json()["decisions"])


async def test_decide_and_ask_person_take_one_of_the_bots_decisions_and_items_that_are_objects(
    served: Served, ana: Person
) -> None:
    bot = await made_bot(served, ana)
    bad: list[dict[str, Any]] = [
        {"decision": "nope", "items": MAIL}, {"items": MAIL}, {"decision": "worth"}, {"decision": "worth", "items": []},
        {"decision": "worth", "items": "m1"}, {"decision": "worth", "items": ["m1"]},
        {"decision": "worth", "items": [{"id": n} for n in range(deciding.ITEMS_MAX + 1)]},
    ]  # fmt: skip
    asks = [(ASK, {"question": "Which?", **b}) for b in bad[:2]]
    go = play(*((DECIDE, b) for b in bad), *asks, (ASK, {}), (ASK, {"question": " "}), text="I could not decide.")
    served.agent.script = [go]
    run = await ran(served, ana, bot["slug"], "Decide")
    no_question = Outcome(ERROR, "ask_person takes the question to ask.")
    assert go.heard == [Outcome(ERROR, BAD)] * (len(bad) + 2) + [no_question] * 2  # type: ignore[attr-defined]
    assert run["status"] == "done" and run["steps"] == [] and await listed(served, ana, bot["slug"]) == []


async def test_what_ada_is_sure_of_is_kept_and_a_wrong_one_corrected(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana)
    sure(served, lambda case: ("answer", 0.95) if "Lunch" in case["m"]["s"]["subject"] else ("skip", 0.9))
    later = {"decision": "worth", "items": [{"id": "m3", "subject": "Lunch again?"}]}
    go = play((DECIDE, ITEMS), (DECIDE, later), text="Two to answer.")
    served.agent.script = [go]
    run = await ran(served, ana, bot["slug"], "What is worth answering?")
    assert go.heard[0].value == [  # type: ignore[attr-defined]
        {"id": "m1", "item": "Lunch on Friday?", "outcome": "answer", "by": "ada", "confidence": 0.95, "sure": True},
        {"id": "m2", "item": "You won!", "outcome": "skip", "by": "ada", "confidence": 0.9, "sure": True},
    ]
    assert run["status"] == "done" and run["question"] is None
    assert [x["title"] for x in run["steps"]] == ["Decided worth for 2 items", "Decided worth for 1 item"]
    assert [x["app"] for x in run["steps"]] == ["Ada", "Ada"] and run["log"] == [x["title"] for x in run["steps"]]
    assert [d["id"] for d in run["data"]["worth"]["decisions"]] == ["m1", "m2", "m3"]  # the run's answers, together
    kept = {d["label"]: (d["now"], d["who"], d["run_id"]) for d in await listed(served, ana, bot["slug"])}
    assert kept == {
        "Lunch on Friday?": ("answer", "ada", run["id"]), "You won!": ("skip", "ada", run["id"]),
        "Lunch again?": ("answer", "ada", run["id"]),
    }  # fmt: skip
    assert len(served.ada.cases[GATE]) == 1  # Ada's own calls are not precedents
    fix = {"outcome": "answer", "gate": "worth", "item": "m2"}
    res = await served.http.post(f"/v1/bot-runs/{run['id']}/wrong", json=fix, headers=ana.headers)
    assert res.status_code == 200 and (res.json()["said"], res.json()["now"]) == ("skip", "answer"), res.text
    assert served.ada.outcomes(GATE)[-1] == "answer"


async def test_what_ada_is_unsure_of_the_bot_asks_the_person_about_and_ada_learns_their_answers(
    served: Served, ana: Person
) -> None:
    bot = await made_bot(served, ana, connections=[])
    mail = [*MAIL, {"id": "m3", "subject": "Coffee?"}]
    items = {"decision": "worth", "items": mail}
    go = play((DECIDE, items), (ASK, {"question": "", **items}))
    served.agent.script = [go, play(text="One to answer.")]
    run = await ran(served, ana, bot["slug"], "What is worth answering?")  # Ada holds nothing yet: every item is new
    assert [(r["outcome"], r["sure"]) for r in go.heard[0].value] == [(None, False)] * 3  # type: ignore[attr-defined]
    asked = run["question"]
    new = (None, None, "no precedents yet")
    assert asked["question"] == "Worth answering?" and asked["decision"] == "worth"  # the decision's own question
    assert [(b["n"], b["guess"], b["p"], b["why"]) for b in asked["batch"]] == [(1, *new), (2, *new), (3, *new)]
    assert asked["answer_with"] == "1=answer 2=skip rest=skip" and run["steps"] == []  # nothing unsure is kept
    done = await answered(served, ana, run["id"], "1=answer rest=skip")
    assert served.ada.outcomes(GATE) == ["answer", "skip", "skip"] and done["output"] == "One to answer."
    assert "Lunch on Friday? (id m1): answer; You won! (id m2): skip" in served.agent.turns[1].message
    assert [x["title"] for x in done["steps"]] == ["Decided worth for 3 items"]
    assert sorted((d["who"], d["now"]) for d in await listed(served, ana, bot["slug"])) == [
        ("you", "answer"), ("you", "skip"), ("you", "skip"),
    ]  # fmt: skip


async def test_a_decision_the_world_answers_keeps_the_persons_answer_but_learns_nothing(
    served: Served, ana: Person
) -> None:
    gate = {**inbox()["gates"]["worth"], "world": True, "question": ""}
    bot = await made_bot(served, ana, spec=inbox(gates={"worth": gate}), connections=[])
    sure(served, lambda case: ("answer", 0.3))
    one = {"decision": "worth", "items": MAIL[:1]}
    served.agent.script = [play((ASK, {"question": "Worth answering?", **one})), play(text="Skip it.")]
    run = await ran(served, ana, bot["slug"], "Worth it?")
    assert run["question"]["question"] == "Worth answering?" and run["question"]["batch"][0]["guess"] == "answer"
    done = await answered(served, ana, run["id"], "skip")
    assert done["data"]["worth"]["decisions"][0]["by"] == "you" and len(served.ada.cases[GATE]) == 1
    assert [(d["who"], d["now"], d["recorded"]) for d in await listed(served, ana, bot["slug"])] == [
        ("you", "skip", False)
    ]


async def test_the_bot_asks_the_person_its_own_question_and_carries_on_with_their_words(
    served: Served, ana: Person
) -> None:
    bot = await made_bot(served, ana, spec={}, connections=[])
    pick = {"question": "Which channel?", "options": ["#team", "#Releases", " "]}
    served.agent.script = [play((ASK, pick), ("never", {})), play((ASK, {"question": "Anything else?"})), play()]
    run = await ran(served, ana, bot["slug"], "Post it")
    asked = run["question"]
    assert (asked["question"], asked["options"], asked["approval"]) == ("Which channel?", ["#team", "#Releases"], False)
    wrong = await served.http.post(f"/v1/bot-runs/{run['id']}/answer", json={"answer": "#ops"}, headers=ana.headers)
    assert wrong.status_code == 422 and "#team, #Releases" in wrong.text
    again = await answered(served, ana, run["id"], "#releases")
    assert "The person answered: #Releases." in served.agent.turns[1].message
    assert again["question"]["options"] == []  # an open question: any words answer it
    done = await answered(served, ana, run["id"], "  Tag the release notes too.  ")
    assert done["status"] == "done" and "answered: Tag the release notes too." in served.agent.turns[2].message


def a_runner(tmp_path: Path, **gate: Any) -> Any:
    """The SDK's runner as deciding.py uses it: the bot's decisions, its Ada, and its real store."""
    fake = FakeAda()
    fake.create_model("m-made", WORTH_SPEC)
    made = {"case": {"m": {"s": {"subject": "$item.subject"}}}, "outcomes": ["some", "fully"], **gate}
    bot = SimpleNamespace(gates={"made": made}, gate_model=lambda name: f"m-{name}")
    return SimpleNamespace(bot=bot, ada=fake, store=RunStore(tmp_path))


def test_a_probed_decision_calls_an_item_unlike_all_it_holds_none_of_its_outcomes(tmp_path: Path) -> None:
    runner = a_runner(tmp_path, probe=True)
    items = [{"id": "a", "subject": "generated"}, {"id": "b", "subject": "written by hand"}]
    fresh = deciding.judged(runner, "r1", "made", items)
    assert [e["by"] for e in fresh] == ["unsure", "unsure"]  # never measured: it has no reference to probe by
    runner.store.set_state(probe.KEY + "made", json.dumps({probe.FLOOR: 0.6, "n": 9}))
    none_held = deciding.judged(runner, "r1", "made", items)
    assert [(e["by"], e["outcome"], e["mode"]) for e in none_held] == [("probe", "human", "probe")] * 2
    runner.ada.cases["m-made"].append(({}, "fully"))
    runner.ada.rule["m-made"] = lambda case: ("fully", 0.9)
    runner.ada.near["m-made"] = lambda case: 0.9 if "generated" in case["m"]["s"]["subject"] else 0.2
    judged = deciding.judged(runner, "r1", "made", items)
    assert [(e["by"], e["outcome"], e["p"]) for e in judged] == [("ada", "fully", 0.9), ("probe", "human", None)]
    assert [(r["by"], r["sure"]) for r in deciding.results(judged)] == [("ada", True), ("ada", True)]
    run = deciding.kept(runner, "", "made", judged)
    assert run and [d["key"] for d in runner.store.decisions(run=run)] == ["a"]  # what the probe said is no decision
    data = runner.store.get(run)["data"]
    assert data["made-1"] == {"fully": [items[0]]} and data["_gates"]["made"] == {"each": True, "by": "ada", "asked": 0}
    (tmp_path / "plain").mkdir()
    plain = a_runner(tmp_path / "plain")
    plain.store.set_state(probe.KEY + "made", json.dumps({probe.FLOOR: 0.6}))
    assert [e["by"] for e in deciding.judged(plain, "r1", "made", items)] == ["unsure", "unsure"]  # not probed
