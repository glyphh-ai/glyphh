"""A program's code step (docs/specs/programs.md, 3): its function sent to the program's rrotor (glyphh_bot's `code`,
rrotor 0.10.0), the run dispatched until the result lands over the link, then walked on; refused in plain words on
Glyphh cloud, on an older rrotor and on one that is not linked; cancelled on the rrotor too."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.ops.link.protocol import Call, Cancel
from glyphh_server.ops.programs import code
from tests.bots.conftest import made_bot
from tests.bots.programs import made, ran, run_of, trail
from tests.bots.remote import OnRrotor, online, rrotor_fixture  # noqa: F401 (the fixture)
from tests.db.helpers import person

SOURCE: str = '''"""Counts."""

FLOW = [
    {"id": "count", "kind": "code", "function": "count", "input": {"said": "{input}"}, "next": "ask"},
    {"id": "ask", "kind": "ask", "question": "It was {count.n}. Fine?", "options": ["Yes"], "next": None},
]


def count(given):
    return {"n": len(given["said"])}
'''


def result(status: str = "done", **data: Any) -> dict[str, Any]:
    return {"status": status, "step": None, "prompt": None, "data": data}


async def test_a_code_step_runs_on_the_programs_rrotor(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await online(engine, ada, version="0.10.0")
    bot = await made_bot(on_rrotor.s, ada, folders=[{"path": "/srv/mail", "access": "read"}], runs_on=str(rt.id))
    program = await made(on_rrotor.s, ada, None, source=SOURCE, runs_on=str(rt.id), bot=bot["slug"])
    assert program["problems"] == [] and program["can_run_on"] == ["rrotor"]
    out = await ran(on_rrotor.s, ada, said="lunch")
    assert out["status"] == "dispatched" and out["at"] == "count"
    sent = on_rrotor.call()
    assert isinstance(sent, Call) and (sent.program, sent.function, str(sent.run_id)) == (
        "glyphh_bot",
        "code",
        out["id"],
    )
    assert sent.inputs == {"source": SOURCE, "function": "count", "given": {"said": "lunch"}}
    assert sent.folders == [{"path": "/srv/mail", "access": "read"}]
    await on_rrotor.landed(rt, ada, out["id"], result(result={"n": 5}))
    await on_rrotor.landed(rt, ada, out["id"], result(result={"n": 9}))  # a replay: taken once
    await on_rrotor.s.settled()
    waits = await run_of(on_rrotor.s, ada, out["id"])
    assert waits["status"] == "needs_input" and waits["question"]["question"] == "It was 5. Fine?"
    assert (await trail(on_rrotor.s, ada, out["id"]))[1:3] == [
        ("step", "count", "inbox-cat", None, True),  # sent
        ("step", "count", "inbox-cat", None, True),  # ran
    ]


async def test_code_that_fails_or_answers_too_much_fails_the_run(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await online(engine, ada, version="0.10.0")
    await made(on_rrotor.s, ada, None, source=SOURCE, runs_on=str(rt.id), bot=None)
    out = await ran(on_rrotor.s, ada)
    await on_rrotor.landed(rt, ada, out["id"], result("failed", reason="count raised KeyError: 'said'"))
    failed = await run_of(on_rrotor.s, ada, out["id"])
    assert (failed["status"], failed["error"]) == ("failed", "count raised KeyError: 'said'")
    assert code.came({"status": "failed", "data": None}).error == "The code failed on the rrotor."
    assert code.came(result(result="x" * 1_000_001)).error == "The code's result was too large to keep."
    out = await ran(on_rrotor.s, ada)
    res = await on_rrotor.s.http.post(f"/v1/program-runs/{out['id']}/cancel", headers=ada.headers)
    assert res.json()["status"] == "failed" and isinstance(on_rrotor.hub.last(), Cancel)
    await on_rrotor.landed(rt, ada, out["id"], result(result={"n": 1}))  # too late: the run is over
    assert (await run_of(on_rrotor.s, ada, out["id"]))["status"] == "failed"


async def test_code_is_refused_where_it_cannot_run(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada = await person(engine)
    program = await made(on_rrotor.s, ada, None, source=SOURCE, bot=None)  # on Glyphh cloud
    assert program["problems"][0].startswith("count: code does not run on Glyphh cloud yet: choose one of your rrotors")
    res = await on_rrotor.s.http.post("/v1/programs/mail-round/runs", json={}, headers=ada.headers)
    assert res.status_code == 422 and "code does not run on Glyphh cloud yet" in res.json()["error"]["message"]
    old = await online(engine, ada, version="0.9.0")
    await on_rrotor.s.http.patch("/v1/programs/mail-round", json={"runs_on": str(old.id)}, headers=ada.headers)
    failed = await ran(on_rrotor.s, ada)
    assert (
        failed["status"] == "failed"
        and "which cannot run a program's code: update it to rrotor 0.10.0" in failed["error"]
    )
    assert not code.runs_code(None) and code.runs_code("0.10.3") and code.runs_code("1.0.0")
    new = await online(engine, ada, version="0.10.0")
    await on_rrotor.s.http.patch("/v1/programs/mail-round", json={"runs_on": str(new.id)}, headers=ada.headers)
    on_rrotor.hub.up = False
    failed = await ran(on_rrotor.s, ada)
    assert (
        failed["error"]
        == "The program's rrotor is not linked to Glyphh right now: start it, or check its link, then try again."
    )
    off = await online(engine, ada, state="offline", version="0.10.0")
    await on_rrotor.s.http.patch("/v1/programs/mail-round", json={"runs_on": str(off.id)}, headers=ada.headers)
    failed = await ran(on_rrotor.s, ada)
    assert failed["status"] == "failed" and "is not linked to Glyphh right now" in failed["error"]
