"""A bot's decisions, read and trained (docs/specs/bots.md, 12): each gate's call on each item of each run copied from
the runner's state after the go, readable (a label and fields, never JSON), searched, filtered, sorted and paged by
cursor; relabelled, confirmed right and added by hand through the gate's Ada model; a precedent forgotten; the gates'
stats; their nearest precedents; and a backtest of the gates now."""

import uuid
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import BotDecision
from tests.bots.conftest import Served, made_bot
from tests.bots.test_runs import answered, started
from tests.db.helpers import Person, person

GATE = "bot-inbox-cat-gate-worth"
URL = "/v1/bots/inbox-cat/decisions"


async def listed(s: Served, caller: Person, /, **params: Any) -> dict[str, Any]:
    res = await s.http.get(URL, params=params, headers=caller.headers)
    assert res.status_code == 200, res.text
    return dict(res.json())


async def asked_once(s: Served, engine: AsyncEngine) -> tuple[Person, dict[str, Any]]:
    """The inbox bot run once, its gate asking about both letters and the person answering."""
    who = await person(engine)
    await made_bot(s, who)
    run = await answered(s, who, await started(s, who), "1=answer 2=skip")
    return who, run


async def test_a_runs_decisions_are_readable_searched_filtered_sorted_and_paged(
    served: Served, engine: AsyncEngine
) -> None:
    ada, run = await asked_once(served, engine)
    page = await listed(served, ada)
    assert page["total"] == 2 and page["next_cursor"] is None and page["gates"] == {"worth": ["answer", "skip"]}
    shown = {d["label"]: d for d in page["decisions"]}
    lunch = shown["Lunch on Friday?"]
    assert lunch["who"] == "you" and lunch["outcome"] == lunch["now"] == "answer" and lunch["run_id"] == run["id"]
    assert lunch["fields"] == {"id": "m1", "subject": "Lunch on Friday?"} and lunch["kind"] == "each"
    assert lunch["recorded"] and not lunch["confirmed"] and lunch["outcomes"] == ["answer", "skip"]
    assert [d["label"] for d in (await listed(served, ada, q="lunc"))["decisions"]] == ["Lunch on Friday?"]
    assert (await listed(served, ada, q="nothing here"))["total"] == 0
    assert (await listed(served, ada, q="!!"))["total"] == 2  # no words: no search
    assert (await listed(served, ada, gate="worth", outcome="skip"))["decisions"][0]["label"] == "You won!"
    assert (await listed(served, ada, who="ada"))["total"] == 0
    assert (await listed(served, ada, run_id=run["id"]))["total"] == 2
    assert (await listed(served, ada, run_id=str(uuid.uuid4())))["total"] == 0
    assert (await listed(served, ada, corrected="false"))["total"] == 2
    assert (await listed(served, ada, corrected="true"))["total"] == 0
    assert (await listed(served, ada, since="2999-01-01T00:00:00Z"))["total"] == 0
    assert (await listed(served, ada, until="2000-01-01T00:00:00Z"))["total"] == 0
    for sort in ("time", "confidence", "gate", "outcome"):
        for order in ("asc", "desc"):
            first = await listed(served, ada, sort=sort, order=order, limit=1)
            assert first["total"] == 2 and first["next_cursor"]
            rest = await listed(served, ada, sort=sort, order=order, limit=1, cursor=first["next_cursor"])
            assert rest["next_cursor"] is None
            assert {first["decisions"][0]["label"], rest["decisions"][0]["label"]} == set(shown)
    by_outcome = await listed(served, ada, sort="outcome", order="asc")
    assert [d["outcome"] for d in by_outcome["decisions"]] == ["answer", "skip"]
    cursor = (await listed(served, ada, sort="gate", limit=1))["next_cursor"]
    for bad in ("not-a-cursor", cursor):
        res = await served.http.get(URL, params={"cursor": bad, "sort": "time"}, headers=ada.headers)
        assert res.status_code == 422 and res.json()["error"]["reason"] == "cursor"


async def test_relabel_confirm_and_bulk_learn_through_the_gate(served: Served, engine: AsyncEngine) -> None:
    ada, _ = await asked_once(served, engine)
    ids = {d["label"]: d["id"] for d in (await listed(served, ada))["decisions"]}
    res = await served.http.post(f"/v1/bot-decisions/{ids['You won!']}/relabel", json={"outcome": "answer"},
                                 headers=ada.headers)  # fmt: skip
    assert res.status_code == 200, res.text
    fixed = res.json()
    assert fixed["decisions"][0]["corrected"] == "answer" and fixed["decisions"][0]["now"] == "answer"
    assert fixed["precedents"] == 3 and "relabelled answer" in fixed["said"]
    assert served.ada.outcomes(GATE)[-1] == "answer"
    assert (await listed(served, ada, corrected="true"))["decisions"][0]["label"] == "You won!"
    again = await served.http.post(f"/v1/bot-decisions/{ids['You won!']}/relabel", json={"outcome": "skip"},
                                   headers=ada.headers)  # fmt: skip
    assert again.json()["precedents"] == 3 and served.ada.outcomes(GATE)[-1] == "skip"  # its own precedent, graded
    bad = await served.http.post(f"/v1/bot-decisions/{ids['You won!']}/relabel", json={"outcome": "maybe"},
                                 headers=ada.headers)  # fmt: skip
    assert bad.status_code == 422 and bad.json()["error"]["reason"] == "outcome"
    sure = await served.http.post(f"/v1/bot-decisions/{ids['Lunch on Friday?']}/confirm", headers=ada.headers)
    assert sure.json()["decisions"][0]["confirmed"] and sure.json()["precedents"] == 3  # the person's: one already
    both = list(ids.values())
    many = await served.http.post(f"{URL}/relabel", json={"ids": both, "outcome": "skip"}, headers=ada.headers)
    assert [d["now"] for d in many.json()["decisions"]] == ["skip", "skip"]
    kept = await served.http.post(f"{URL}/confirm", json={"ids": both}, headers=ada.headers)
    assert kept.status_code == 200 and all(d["confirmed"] for d in kept.json()["decisions"])
    gone = await served.http.post(f"{URL}/confirm", json={"ids": [str(uuid.uuid4())]}, headers=ada.headers)
    assert gone.status_code == 404
    missing = await served.http.post(f"/v1/bot-decisions/{uuid.uuid4()}/confirm", headers=ada.headers)
    assert missing.status_code == 404


async def _row(engine: AsyncEngine, who: Person, bot_id: str, **over: Any) -> uuid.UUID:
    """A decision straight in the table, as one a run left (another gate, or one the runner no longer has)."""
    row = {"org_id": who.org_id, "bot_id": uuid.UUID(bot_id), "loop_run": "gone-run", "gate": "worth", "step": "worth",
           "n": 1, "key": uuid.uuid4().hex, "kind": "each", "label": "Old letter",
           "case": {"m": {"s": {"subject": "x"}}}, "outcome": "skip", "who": "ada", "p": 0.9,
           "body": "Old letter", **over}  # fmt: skip
    async with engine.begin() as conn:
        made = await conn.execute(insert(BotDecision).values(**row).returning(BotDecision.id))
        return made.scalar_one()


async def test_a_sure_call_is_confirmed_into_a_precedent_and_gates_are_one_at_a_time(
    served: Served, engine: AsyncEngine
) -> None:
    ada = await person(engine)
    bot = await made_bot(served, ada)
    served.ada.cases[GATE].append(({}, "skip"))
    served.ada.rule[GATE] = lambda case: ("answer", 0.95) if "Lunch" in case["m"]["s"]["subject"] else ("skip", 0.95)
    await started(served, ada)
    page = await listed(served, ada, who="ada")
    assert page["total"] == 2 and {d["confidence"] for d in page["decisions"]} == {0.95}
    ids = [d["id"] for d in page["decisions"]]
    kept = await served.http.post(f"{URL}/confirm", json={"ids": ids}, headers=ada.headers)
    assert kept.json()["precedents"] == 3 and sorted(served.ada.outcomes(GATE)[1:]) == ["answer", "skip"]
    assert all(d["recorded"] for d in kept.json()["decisions"])
    stats = (await served.http.get(f"{URL}/stats", headers=ada.headers)).json()["gates"][0]
    assert stats["accuracy"] == 1.0 and stats["ask_rate"] == 0.0 and stats["confirmed"] == 2
    orphan = await _row(engine, ada, bot["id"])
    alone = await served.http.post(f"/v1/bot-decisions/{orphan}/confirm", headers=ada.headers)
    assert alone.json()["decisions"][0]["confirmed"]  # recorded in Ada; the runner has no record of it to mark
    other = await _row(engine, ada, bot["id"], gate="other")
    mixed = await served.http.post(f"{URL}/relabel", json={"ids": [ids[0], str(other)], "outcome": "skip"},
                                   headers=ada.headers)  # fmt: skip
    assert mixed.status_code == 422 and "one gate at a time" in mixed.json()["error"]["message"]
    nogate = await served.http.post(f"/v1/bot-decisions/{other}/relabel", json={"outcome": "skip"}, headers=ada.headers)
    assert nogate.status_code == 422 and nogate.json()["error"]["reason"] == "gate"
    shown = (await served.http.get(f"/v1/bot-decisions/{other}", headers=ada.headers)).json()
    assert shown["precedents"] == [] and shown["case"] == {"m": {"s": {"subject": "x"}}}  # its gate is gone


async def test_cases_by_hand_precedents_forgotten_and_nearest(served: Served, engine: AsyncEngine) -> None:
    ada, _ = await asked_once(served, engine)
    item = {"id": "m9", "subject": "Board meeting moved"}
    res = await served.http.post("/v1/bots/inbox-cat/cases", json={"gate": "worth", "outcome": "answer", "item": item},
                                 headers=ada.headers)  # fmt: skip
    assert res.status_code == 201, res.text
    added = res.json()["decisions"][0]
    assert added["kind"] == "case" and added["who"] == "you" and added["label"] == "Board meeting moved"
    assert served.ada.cases[GATE][-1] == ({"m": {"s": {"subject": "Board meeting moved", "id": "m9"}}}, "answer")
    raw = {"gate": "worth", "outcome": "skip", "case": {"m": {"s": {"subject": "Spam"}}}, "label": "A spam letter"}
    by_case = (await served.http.post("/v1/bots/inbox-cat/cases", json=raw, headers=ada.headers)).json()
    assert by_case["decisions"][0]["label"] == "A spam letter" and by_case["precedents"] == 4
    for body in ({"gate": "worth", "outcome": "skip"}, {"gate": "nope", "outcome": "skip", "item": item}):
        bad = await served.http.post("/v1/bots/inbox-cat/cases", json=body, headers=ada.headers)
        assert bad.status_code == 422

    served.ada.rule[GATE] = lambda case: ("answer", 0.9)  # the fake's nearest precedent is always p1
    near = (await served.http.get(f"/v1/bot-decisions/{added['id']}", headers=ada.headers)).json()
    assert near["precedents"][0] == {"id": "p1", "outcome": "answer", "similarity": 1.0, "label": None,
                                     "decision_id": None}  # fmt: skip
    assert near["fields"]["subject"] == "Board meeting moved"
    relabel = await served.http.post(f"/v1/bot-decisions/{added['id']}/relabel", json={"outcome": "skip"},
                                     headers=ada.headers)  # fmt: skip
    assert relabel.json()["decisions"][0]["corrected"] == "skip"  # its precedent graded again

    pid = added["id"]
    precedent = (await served.http.get(f"/v1/bot-decisions/{pid}", headers=ada.headers)).json()
    forget = f"/v1/bots/inbox-cat/gates/worth/precedents/{precedent['precedents'][0]['id']}"
    gone = await served.http.delete(forget, headers=ada.headers)
    assert gone.status_code == 200 and gone.json()["gate"] == "worth" and "p1" in served.ada.forgotten
    lost = (await listed(served, ada))["decisions"]
    letter = next(d for d in lost if d["label"] == "You won!")
    fixed = await served.http.post(f"/v1/bot-decisions/{letter['id']}/relabel", json={"outcome": "answer"},
                                   headers=ada.headers)  # fmt: skip
    its = fixed.json()["decisions"][0]
    detail = (await served.http.get(f"/v1/bot-decisions/{its['id']}", headers=ada.headers)).json()
    assert detail["recorded"]
    mine = await _precedent_of(engine, its["id"])
    assert (await served.http.delete(f"/v1/bots/inbox-cat/gates/worth/precedents/{mine}", headers=ada.headers)).json()
    after = next(d for d in (await listed(served, ada))["decisions"] if d["id"] == its["id"])
    assert not after["recorded"]
    by_hand = await _precedent_of(engine, by_case["decisions"][0]["id"])
    await served.http.delete(f"/v1/bots/inbox-cat/gates/worth/precedents/{by_hand}", headers=ada.headers)
    assert by_case["decisions"][0]["id"] not in {d["id"] for d in (await listed(served, ada))["decisions"]}
    nogate = await served.http.delete("/v1/bots/inbox-cat/gates/nope/precedents/p1", headers=ada.headers)
    assert nogate.status_code == 422
    assert (await served.http.get(f"/v1/bot-decisions/{uuid.uuid4()}", headers=ada.headers)).status_code == 404


async def _precedent_of(engine: AsyncEngine, decision_id: str) -> str:
    from sqlalchemy import select

    async with engine.begin() as conn:
        found = select(BotDecision.precedent).where(BotDecision.id == uuid.UUID(decision_id))
        return str((await conn.execute(found)).scalar_one())


async def test_gate_stats_and_a_backtest_of_the_gates_now(served: Served, engine: AsyncEngine) -> None:
    ada, _ = await asked_once(served, engine)
    ids = {d["label"]: d["id"] for d in (await listed(served, ada))["decisions"]}
    await served.http.post(f"/v1/bot-decisions/{ids['You won!']}/relabel", json={"outcome": "answer"},
                           headers=ada.headers)  # fmt: skip
    stats = (await served.http.get(f"{URL}/stats", headers=ada.headers)).json()["gates"]
    worth = stats[0]
    assert worth["gate"] == "worth" and worth["decisions"] == 2 and worth["by"] == {"ada": 0, "you": 2, "default": 0}
    assert worth["ask_rate"] == 1.0 and worth["corrected"] == 1 and worth["accuracy"] is None
    assert len(worth["days"]) == 1 and worth["days"][0]["decisions"] == 2
    one = (await served.http.get(f"{URL}/stats", params={"gate": "worth", "days": 7}, headers=ada.headers)).json()
    assert [g["gate"] for g in one["gates"]] == ["worth"]

    served.ada.rule[GATE] = lambda case: ("answer", 0.95)
    res = await served.http.post("/v1/bots/inbox-cat/backtest", json={"limit": 10}, headers=ada.headers)
    done = res.json()
    assert res.status_code == 200 and done["replayed"] == 2 and done["would_ask"] == 0 and done["right_now"] == 2
    assert done["same"] == 2 and done["changed"] == []
    served.ada.rule[GATE] = lambda case: ("skip", 0.5)
    unsure = (await served.http.post("/v1/bots/inbox-cat/backtest", json={"gate": "worth"}, headers=ada.headers)).json()
    assert unsure["would_ask"] == 2 and len(unsure["changed"]) == 2 and unsure["changed"][0]["ask"]
    bad = await served.http.post("/v1/bots/inbox-cat/backtest", json={"gate": "nope"}, headers=ada.headers)
    assert bad.status_code == 422
