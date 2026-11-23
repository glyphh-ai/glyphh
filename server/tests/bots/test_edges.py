"""The bots' edges: Pipedream failing every way it can, a run that fails outside its turn, a run cut off by the server
stopping (and one that waited, carried on after it), and a server that starts without its database."""

import asyncio
import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.config import Settings
from glyphh_server.errors import Unavailable
from glyphh_server.ops.bots import props, runs
from glyphh_server.ops.bots.agent import session
from glyphh_server.ops.bots.agent.turn import Ended, Turn
from glyphh_server.ops.bots.pipedream import Pipedream
from tests.bots.agents import SESSION, play
from tests.bots.conftest import BOTS, DECIDE, SEND, Served, answered, connected, made_bot, ran, run_of, serve
from tests.bots.fakes import MAIL, FakePipedream
from tests.db.helpers import Person

REPLY: dict[str, Any] = {"to": ["grace@navy.test"], "subject": "Re: Lunch", "body": "Happy to."}
LINE: dict[str, Any] = {"type": "user", "uuid": "u-1"}


async def test_pipedream_down_or_unreachable_is_unavailable_and_a_refusal_invalid(served: Served, ana: Person) -> None:
    gmail = await connected(served, ana)
    for mode, status in (("down", 503), ("broken", 503), ("refusing", 422)):
        served.pd.mode = mode
        res = await served.http.delete(f"/v1/connections/{gmail['id']}", headers=ana.headers)
        assert res.status_code == status, (mode, res.text)
    served.pd.mode = ""
    served.pd.accounts = []  # gone at Pipedream already: deleting it here still works
    assert (await served.http.delete(f"/v1/connections/{gmail['id']}", headers=ana.headers)).status_code == 204


async def test_pipedream_off_refuses_before_any_call() -> None:
    pd = Pipedream(httpx.AsyncClient(), Settings(secret_key="x" * 32))
    with pytest.raises(Unavailable):
        await pd.apps(None, None)


def test_an_action_without_an_app_prop_is_run_with_the_callers_values_only() -> None:
    defined = [{"name": "q", "type": "string"}]
    assert props.configured(defined, "apn_1", {"q": "x", "other": 1}) == {"q": "x"}


async def test_a_run_that_fails_outside_its_turn_says_why_and_its_session_goes(
    served: Served, ana: Person, engine: AsyncEngine
) -> None:
    bot = await made_bot(served, ana, connections=[])
    seen: list[Any] = []

    def no_ada(key: str) -> Any:
        raise RuntimeError("socket closed")

    async def go(turn: Turn) -> Ended:
        await turn.store.append({"session_id": SESSION}, [LINE])  # as the SDK mirrors the turn while it runs
        seen.append(await turn.store.load({"session_id": SESSION}))
        return await play((DECIDE, {"decision": "worth", "items": MAIL}))(turn)

    served.app.state.bots.ada_for = no_ada
    served.agent.script = [go]
    run = await ran(served, ana, bot["slug"], "What is worth answering?")
    assert (run["status"], run["error"]) == ("failed", "The run failed: RuntimeError: socket closed")
    assert run["summary"] == "It failed: The run failed: RuntimeError: socket closed." and run["finished_at"]
    store = session.Sessions(engine, ana.org_id, uuid.UUID(run["id"]))
    assert seen == [[LINE]] and await store.load({"session_id": SESSION}) is None
    res = await served.http.post(f"/v1/bot-runs/{run['id']}/wrong", json={"outcome": "skip"}, headers=ana.headers)
    assert res.status_code == 422 and "decided nothing with Ada" in res.json()["error"]["message"]


async def test_a_stopped_server_cuts_off_the_run_that_was_going_and_one_that_waited_carries_on_after(
    engine: AsyncEngine, ana: Person
) -> None:
    begun = asyncio.Event()

    async def holding(turn: Turn) -> Ended:
        await turn.store.append({"session_id": SESSION}, [LINE])
        begun.set()
        await asyncio.Event().wait()  # never: the server stops first
        raise AssertionError("unreachable")

    async for s in serve(BOTS, FakePipedream()):
        gmail = await connected(s, ana, allow=False)
        scopes = [{"connection_id": gmail["id"], "tools": ["gmail-send-email"]}]
        asker = await made_bot(s, ana, name="Asker", connections=scopes)
        s.agent.script = [play((SEND, REPLY))]
        waits = await ran(s, ana, asker["slug"], "Reply to Grace")
        assert waits["status"] == "needs_input"
        worker = await made_bot(s, ana, name="Worker", connections=[])
        s.agent.script = [holding]
        going = await s.http.post(f"/v1/bots/{worker['slug']}/runs", json={"input": "x"}, headers=ana.headers)
        await begun.wait()
    kept = session.Sessions(engine, ana.org_id, uuid.UUID(going.json()["id"]))
    assert await kept.load({"session_id": SESSION}) == [LINE]
    async for s in serve(BOTS, FakePipedream()):  # the server starts again (a deploy, a restart)
        cut = await run_of(s, ana, going.json()["id"])
        assert (cut["status"], cut["error"]) == ("failed", "interrupted by a restart") and cut["finished_at"]
        assert cut["summary"] == "It was cut off by a restart before it finished. Run it again."
        assert await kept.load({"session_id": SESSION}) is None  # its session went with it
        assert (await run_of(s, ana, waits["id"]))["status"] == "needs_input"  # a run that waits is not cut off
        s.agent.script = [play((SEND, REPLY), text="Sent.")]
        done = await answered(s, ana, waits["id"], "yes")
        assert (done["status"], done["output"]) == ("done", "Sent.") and len(s.pd.runs) == 1
        assert s.agent.turns[0].session == SESSION and "said yes" in s.agent.turns[0].message  # its own session
        assert await s.app.state.bots.recover() == 0  # nothing more of this machine's was cut off


async def test_a_server_whose_database_is_away_starts_anyway(served: Served, monkeypatch: pytest.MonkeyPatch) -> None:
    async def away(*_: Any) -> int:
        raise ConnectionRefusedError("the database is away")

    monkeypatch.setattr(runs, "recover", away)
    assert await served.app.state.bots.recover() == 0
