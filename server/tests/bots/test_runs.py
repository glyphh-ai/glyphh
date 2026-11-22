"""A bot's runs, end to end with Pipedream, Ada and Claude faked: the SDK's loop walks the inbox bot's steps (a scoped
tool run as the org, a gate over the mail asking the person as one batch, Claude drafting, an approval before the
send), each stop for the person waits until it is answered, the gate learns from the answers, and a wrong call is
corrected."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.bots.conftest import Served, made_bot
from tests.db.helpers import Person, person


async def started(s: Served, who: Person, given: str = "is:unread", slug: str = "inbox-cat") -> dict[str, Any]:
    res = await s.http.post(f"/v1/bots/{slug}/runs", json={"input": given}, headers=who.headers)
    assert res.status_code == 202, res.text
    assert res.json()["status"] == "queued"
    await s.settled()
    return dict((await s.http.get(f"/v1/bot-runs/{res.json()['id']}", headers=who.headers)).json())


async def answered(s: Served, who: Person, run: dict[str, Any], answer: Any) -> dict[str, Any]:
    res = await s.http.post(f"/v1/bot-runs/{run['id']}/answer", json={"answer": answer}, headers=who.headers)
    assert res.status_code == 202, res.text
    await s.settled()
    return dict((await s.http.get(f"/v1/bot-runs/{run['id']}", headers=who.headers)).json())


async def test_a_run_asks_learns_drafts_waits_for_a_yes_and_sends(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    bot = await made_bot(served, ada)
    run = await started(served, ada)
    assert run["status"] == "needs_input" and run["error"] == ""
    asked = run["question"]
    assert asked["options"] == ["answer", "skip"] and [b["label"] for b in asked["batch"]] == [
        "Lunch on Friday?",
        "You won!",
    ]
    assert asked["answer_with"] == "1=answer 2=skip"
    assert served.pd.runs[0]["id"] == "gmail-find-email" and served.pd.runs[0]["configured_props"]["q"] == "is:unread"
    assert served.pd.runs[0]["external_user_id"] == f"org_{ada.org_id}"

    run = await answered(served, ada, run, "1=answer 2=skip")
    assert run["status"] == "needs_input" and "send the reply" in run["question"]["question"]
    assert run["question"]["options"] == ["yes", "no"]
    assert served.ada.outcomes("bot-inbox-cat-gate-worth") == ["answer", "skip"]
    assert served.ada.cases["bot-inbox-cat-gate-worth"][0][0] == {
        "m": {"s": {"subject": "Lunch on Friday?", "id": "m1"}}
    }
    sent = served.claude.requests[0]
    assert sent["model"] == "claude-opus-5-5" and sent["system"].startswith("You are Inbox Cat.")
    assert "One paragraph, no sign-off." in sent["messages"][0]["content"]
    assert len(served.pd.runs) == 1  # nothing sent before the yes

    run = await answered(served, ada, run, "yes")
    assert run["status"] == "done" and run["question"] is None and run["finished_at"]
    assert served.pd.runs[1]["id"] == "gmail-send-email"
    assert served.pd.runs[1]["configured_props"]["body"] == "Happy to, see you Friday."
    assert run["data"]["send"]["ret"] == {"id": "msg_1"} and '"msg_1"' in run["output"]
    assert (run["input_tokens"], run["output_tokens"], run["own_key"]) == (1000, 200, False)
    assert any("gmail-send-email" in line for line in run["log"])
    assert set(served.claude.keys) == {"sk-ant-glyphh-test-key"}
    assert len(set(served.ada.keys)) == 1 and served.ada.keys[0].startswith("glyphh_ak_")
    assert bot["gate_models"][0] == "bot-inbox-cat-gate-worth"


async def test_a_gate_that_is_sure_asks_nothing_and_a_no_ends_the_run(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    served.ada.cases["bot-inbox-cat-gate-worth"].append(({}, "skip"))  # it decides alone once it holds one
    served.ada.rule["bot-inbox-cat-gate-worth"] = lambda case: (
        ("answer", 0.95) if "Lunch" in case["m"]["s"]["subject"] else ("skip", 0.95)
    )
    run = await started(served, ada)
    assert run["status"] == "needs_input" and run["question"]["options"] == ["yes", "no"]
    assert [d["by"] for d in run["data"]["worth"]["decisions"]] == ["ada", "ada"]
    run = await answered(served, ada, run, "no")
    assert run["status"] == "done" and "said no" in run["error"] and len(served.pd.runs) == 1


async def test_nothing_worth_it_ends_the_run_and_wrong_teaches_the_gate(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    served.pd.mail = [{"id": "m3", "subject": "Newsletter"}]
    run = await started(served, ada)
    run = await answered(served, ada, run, "skip")
    assert run["status"] == "done" and "the run ends here" in run["error"]
    # what the person is told is a plain sentence in the bot's own names, and what the bot takes (ops/bots/said.py)
    assert run["summary"].startswith("It decided 1 (1 skip and 0 answer); none came out answer, so it stopped before")
    assert run["hint"].startswith("Inbox Cat does one job: answers the mail worth answering.")
    assert (run["links"], run["apps"]) == ([], [])
    listed = (await served.http.get("/v1/bots/inbox-cat/runs", headers=ada.headers)).json()["runs"][0]
    assert listed["summary"] == run["summary"]
    res = await served.http.post(
        f"/v1/bot-runs/{run['id']}/wrong", json={"outcome": "answer", "item": "m3"}, headers=ada.headers
    )
    assert res.status_code == 200, res.text
    assert (res.json()["said"], res.json()["now"]) == ("skip", "answer")
    assert served.ada.outcomes("bot-inbox-cat-gate-worth") == ["skip", "answer"]
    bad = await served.http.post(f"/v1/bot-runs/{run['id']}/wrong", json={"outcome": "maybe"}, headers=ada.headers)
    assert bad.status_code == 422 and bad.json()["error"]["reason"] == "wrong"
    gates = (await served.http.get("/v1/bots/inbox-cat/gates", headers=ada.headers)).json()["gates"]
    assert gates["worth"]["precedents"] == 2


async def test_one_live_run_a_bot_answers_that_do_not_fit_and_cancelling(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    run = await started(served, ada)
    again = await served.http.post("/v1/bots/inbox-cat/runs", json={}, headers=ada.headers)
    assert again.status_code == 409 and again.json()["error"]["code"] == "E_CONFLICT"
    for wrong in ("1=maybe", "nonsense"):
        res = await served.http.post(f"/v1/bot-runs/{run['id']}/answer", json={"answer": wrong}, headers=ada.headers)
        assert res.status_code == 422 and res.json()["error"]["reason"] == "answer"
    res = await served.http.post(f"/v1/bot-runs/{run['id']}/cancel", headers=ada.headers)
    assert res.status_code == 200 and (res.json()["status"], res.json()["error"]) == ("failed", "cancelled")
    for path in ("answer", "cancel"):
        body = {"answer": "yes"} if path == "answer" else None
        res = await served.http.post(f"/v1/bot-runs/{run['id']}/{path}", json=body, headers=ada.headers)
        assert res.status_code == 409
    nothing = await served.http.post(f"/v1/bot-runs/{run['id']}/wrong", json={"outcome": "skip"}, headers=ada.headers)
    assert nothing.status_code == 422  # it passed the gate, but asked, and was never answered
    assert (await started(served, ada))["status"] == "needs_input"  # the cancelled run is not the one carried on


async def test_a_single_answer_and_runs_listed(served: Served, engine: AsyncEngine) -> None:
    ada = await person(engine)
    await made_bot(served, ada)
    served.pd.mail = [{"id": "m4", "subject": "Coffee?"}]
    run = await started(served, ada)
    run = await answered(served, ada, run, ["answer"])
    assert run["question"]["options"] == ["yes", "no"]
    run = await answered(served, ada, run, " YES ")
    assert run["status"] == "done"
    listed = (await served.http.get("/v1/bots/inbox-cat/runs", headers=ada.headers)).json()["runs"]
    assert [r["id"] for r in listed] == [run["id"]]
