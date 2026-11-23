"""A program run's edges (docs/specs/programs.md, 2): a run cancelled while a step is going, ended elsewhere
meanwhile, a step that crashes, takes too long or is blocked, a step that went from the file while the run waited,
a bot that cannot start, a bot answered at its own run, and the server closing with a run going."""

import asyncio
import dataclasses
from typing import Any

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Conflict
from glyphh_server.models import ProgramRun
from glyphh_server.ops.auth.principal import Principal
from glyphh_server.ops.bots import orchestrator
from glyphh_server.ops.bots.agent.turn import Ended, Turn
from glyphh_server.ops.programs import found, runs, steps
from tests.bots.agents import SESSION, play
from tests.bots.conftest import ASK, Served, made_bot, ran
from tests.bots.market import linked
from tests.bots.programs import FIND_STEP, SEND_STEP, answered, made, run_of
from tests.bots.programs import ran as program_ran
from tests.db.helpers import Person

WRITE: list[dict[str, Any]] = [
    {"id": "write", "kind": "bot", "task": "Plan {input}", "next": "then"},
    {"id": "then", "kind": "bot", "task": "And then?", "next": None},
]


class Held:
    """An agent whose go waits until it is let go."""

    def __init__(self) -> None:
        self.started, self.let = asyncio.Event(), asyncio.Event()

    async def __call__(self, turn: Turn) -> Ended:
        self.started.set()
        await self.let.wait()
        return Ended(text="Planned.", session=SESSION, input_tokens=1, output_tokens=1)


async def _going(s: Served, who: Person, held: Held) -> str:
    """A run whose first step's bot is working: its id."""
    s.agent.script = [held]
    res = await s.http.post("/v1/programs/mail-round/runs", json={"input": "lunch"}, headers=who.headers)
    assert res.status_code == 202, res.text
    await asyncio.wait_for(held.started.wait(), 5)
    return str(res.json()["id"])


@pytest.fixture(autouse=True)
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orchestrator, "EVERY", 0.01)
    monkeypatch.setattr(orchestrator, "WAIT_SECONDS", 0.0)  # a bot step looks again while its bot still works


async def test_a_run_is_cancelled_while_a_step_is_going(served: Served, ana: Person) -> None:
    await made_bot(served, ana)
    await made(served, ana, WRITE)
    held = Held()
    run_id = await _going(served, ana, held)
    res = await served.http.post(f"/v1/program-runs/{run_id}/cancel", headers=ana.headers)
    assert (res.json()["status"], res.json()["error"]) == ("failed", "cancelled")
    held.let.set()
    await served.settled()
    assert (await run_of(served, ana, run_id))["status"] == "failed"
    programs = served.app.state.bots.programs
    programs.spawn(ana.org_id, run_id)  # a go of a run that is over does nothing
    await programs.wait()
    assert (await run_of(served, ana, run_id))["at"] == "write"


async def test_a_run_ended_elsewhere_stops_at_its_next_step(served: Served, ana: Person, engine: AsyncEngine) -> None:
    await made_bot(served, ana)
    await made(served, ana, WRITE)
    held = Held()
    run_id = await _going(served, ana, held)
    async with engine.begin() as conn:
        await conn.execute(update(ProgramRun).where(ProgramRun.id == run_id).values(status="failed", error="elsewhere"))
    held.let.set()
    await served.settled()
    over = await run_of(served, ana, run_id)
    assert (over["status"], over["error"], over["at"]) == ("failed", "elsewhere", "then")
    assert len(served.agent.turns) == 1  # the second step never began


async def test_the_server_closing_stops_the_runs_it_walks(served: Served, ana: Person) -> None:
    await made_bot(served, ana)
    await made(served, ana, WRITE)
    await _going(served, ana, Held())
    programs = served.app.state.bots.programs
    assert len(programs.tasks) == 1
    await programs.close()
    await asyncio.sleep(0)
    assert programs.tasks == {}


async def test_a_step_that_crashes_takes_too_long_or_is_blocked_fails_the_run(
    served: Served, ana: Person, monkeypatch: pytest.MonkeyPatch
) -> None:
    bot = await made_bot(served, ana)
    await made(served, ana, [{"id": "b", "kind": "branch", "on": "{input}", "next": None}])

    def crash(step: Any, outputs: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(steps, "branch", crash)
    assert (await program_ran(served, ana))["error"] == "The run failed: RuntimeError: boom"
    await served.http.patch("/v1/programs/mail-round", json={"flow": [FIND_STEP]}, headers=ana.headers)

    known = steps.tools.of

    async def nap(given: Any) -> None:
        await asyncio.sleep(5)

    async def breaks(given: Any) -> None:
        raise RuntimeError("no such mailbox")

    for call, said in (
        (nap, "Find Email took longer than 0.01 seconds"),
        (breaks, "Find Email failed: no such mailbox"),
    ):

        async def swapped(*args: Any, call: Any = call) -> Any:
            return {n: dataclasses.replace(t, seconds=0.01, call=call) for n, t in (await known(*args)).items()}

        with monkeypatch.context() as patched:
            patched.setattr(steps.tools, "of", swapped)
            assert (await program_ran(served, ana))["error"] == said
    conn = bot["connections"][0]["connection_id"]
    modes = {"permissions": {"gmail-find-email": "deny"}}
    assert (await served.http.put(f"/v1/connections/{conn}/permissions", json=modes, headers=ana.headers)).is_success
    assert (await program_ran(served, ana))["error"].startswith("Find Email is blocked on the Gmail connection.")


async def test_a_step_gone_from_the_file_while_the_run_waited_fails_it(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana)
    conn = bot["connections"][0]["connection_id"]
    modes = {"permissions": {"gmail-send-email": "ask"}}
    assert (await served.http.put(f"/v1/connections/{conn}/permissions", json=modes, headers=ana.headers)).is_success
    await made(served, ana, [SEND_STEP])
    waits = await program_ran(served, ana)
    await served.http.patch("/v1/programs/mail-round", json={"flow": [FIND_STEP]}, headers=ana.headers)
    over = await answered(served, ana, waits["id"], "yes")
    assert (over["status"], over["error"]) == ("failed", "Its step send is no longer in the program.")
    who = Principal(user_id=ana.user_id, org_id=ana.org_id, install_id=ana.install_id, role="admin", email=ana.email)
    row = await runs.shown(served.app.state.bots.engine, ana.org_id, waits["id"])
    with pytest.raises(Conflict, match="not waiting"):  # answered twice at once: the second finds it gone on
        await served.app.state.bots.programs._again(who, row, "yes", {})


async def test_a_bot_that_cannot_start_fails_the_step_and_one_answered_at_its_own_run_wakes_the_program(
    served: Served, ana: Person
) -> None:
    await made_bot(served, ana)
    await made(served, ana, [WRITE[0] | {"next": None}])
    served.agent.script = [play((ASK, {"question": "Which day?", "options": ["Mon", "Fri"]}))]
    busy = await ran(served, ana, "inbox-cat", "hello")  # the bot's own run waits on the person
    failed = await program_ran(served, ana)
    assert failed["status"] == "failed" and failed["error"].startswith("Inbox Cat could not start: ")
    await served.http.post(f"/v1/bot-runs/{busy['id']}/cancel", headers=ana.headers)
    served.agent.script = [play((ASK, {"question": "Which day?", "options": ["Mon", "Fri"]})), play(text="Friday.")]
    waits = await program_ran(served, ana)
    child = waits["question"]["child_run"]
    res = await served.http.post(f"/v1/bot-runs/{child}/answer", json={"answer": "Fri"}, headers=ana.headers)
    assert res.status_code == 202, res.text
    await served.settled()
    done = await run_of(served, ana, waits["id"])
    assert (done["status"], done["outputs"]["write"]) == ("done", "Friday.")


async def test_a_search_stops_at_its_most(served: Served, ana: Person, monkeypatch: pytest.MonkeyPatch) -> None:
    await linked(served, ana, "gmail")
    monkeypatch.setattr(found, "MOST", 1)
    got = (await served.http.get("/v1/tools/search?q=email", headers=ana.headers)).json()["tools"]
    assert [t["key"] for t in got] == ["gmail-send-email"]
