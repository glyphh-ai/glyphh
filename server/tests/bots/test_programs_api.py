"""The org's programs over the API (docs/specs/programs.md, 5 and 6): made from steps or from a file, read back as
both, changed, scheduled and fired by the minute tick, cancelled, deleted; a template's program installed with its
bot; `search_tool` and a found tool added to a bot; and the runs a restart cut off, failed."""

from datetime import UTC, datetime, timedelta
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Program, ProgramRun
from glyphh_server.ops import tend
from glyphh_server.ops.link.hub import Hub
from glyphh_server.ops.programs import due
from tests.bots.conftest import BOTS, Served, made_bot
from tests.bots.market import any_component, installed, linked
from tests.bots.programs import FIND_STEP, answered, made, ran, run_of, trail
from tests.bots.remote import logged
from tests.db.helpers import Person, person

ASK: list[dict[str, Any]] = [{"id": "a", "kind": "ask", "question": "Go {input}?", "options": ["Go"], "next": None}]
FILE: str = (
    '"""Mine."""\n\nFLOW = [{"id": "a", "kind": "ask", "question": "Go?"}]\n\n\ndef count(given):\n    return 1\n'
)


async def test_a_program_is_made_read_changed_and_deleted(served: Served, ana: Person) -> None:
    await made_bot(served, ana)
    got = await made(served, ana, ASK)
    assert (got["slug"], got["bot"], got["flow"], got["problems"]) == ("mail-round", "inbox-cat", ASK, [])
    assert got["source"].startswith('"""A program."""\n\nFLOW = [\n    {"id": "a", "kind": "ask"')
    assert got["can_run_on"] == ["cloud", "rrotor"] and got["last_run"] is None and got["schedule_summary"] == "Off"
    again = await served.http.post("/v1/programs", json={"name": "Mail round"}, headers=ana.headers)
    assert again.status_code == 409
    none = await served.http.post("/v1/programs", json={"name": "X", "bot": "nope"}, headers=ana.headers)
    assert none.status_code == 404 and none.json()["error"]["message"] == "There is no bot 'nope'."
    listed = (await served.http.get("/v1/programs", headers=ana.headers)).json()["programs"]
    assert [p["slug"] for p in listed] == ["mail-round"]
    assert (await served.http.get("/v1/programs?q=zebra", headers=ana.headers)).json()["programs"] == []
    assert len((await served.http.get("/v1/programs?q=reads", headers=ana.headers)).json()["programs"]) == 1
    changed = await served.http.patch(
        "/v1/programs/mail-round", json={"source": FILE, "name": "Rounds", "bot": None}, headers=ana.headers
    )
    now = changed.json()
    assert (now["name"], now["slug"], now["bot"], now["functions"]) == ("Rounds", "mail-round", None, ["count"])
    named = [{"id": "w", "kind": "bot", "bot": "ghost", "task": "t"}, {"id": "c", "kind": "code", "function": "count"}]
    drawn = (await served.http.patch("/v1/programs/mail-round", json={"flow": named}, headers=ana.headers)).json()
    assert drawn["source"].endswith("def count(given):\n    return 1\n") and drawn["can_run_on"] == ["rrotor"]
    assert drawn["problems"] == [
        "w: there is no bot ghost",
        "c: code does not run on Glyphh cloud yet: choose one of your rrotors for this program, and its code runs "
        "there",
    ]
    assert (await served.http.get("/v1/programs/nope", headers=ana.headers)).status_code == 404
    assert (await served.http.delete("/v1/programs/mail-round", headers=ana.headers)).status_code == 204
    assert (await served.http.get("/v1/programs/mail-round", headers=ana.headers)).status_code == 404


async def test_a_run_is_cancelled_and_a_missing_run_is_not_found(served: Served, ana: Person) -> None:
    await made(served, ana, ASK, bot=None)
    waits = await ran(served, ana)
    res = await served.http.post(f"/v1/program-runs/{waits['id']}/cancel", headers=ana.headers)
    assert res.status_code == 200 and (res.json()["status"], res.json()["error"]) == ("failed", "cancelled")
    assert (await trail(served, ana, waits["id"]))[-1] == ("cancelled", "", None, "Ada Lovelace", False)
    again = await served.http.post(f"/v1/program-runs/{waits['id']}/cancel", headers=ana.headers)
    assert again.status_code == 409
    gone = "00000000-0000-0000-0000-000000000000"
    assert (await served.http.get(f"/v1/program-runs/{gone}", headers=ana.headers)).status_code == 404
    assert (await served.http.get(f"/v1/program-runs/{gone}/events", headers=ana.headers)).status_code == 404


async def _due(engine: AsyncEngine, who: Person) -> None:
    async with engine.begin() as conn:
        then = datetime.now(UTC) - timedelta(minutes=1)
        await conn.execute(update(Program).where(Program.org_id == who.org_id).values(next_run_at=then))


async def test_a_scheduled_program_is_fired_by_the_tick_and_logged(
    served: Served, engine: AsyncEngine, redis: Redis
) -> None:
    ada = await person(engine)
    got = await made(served, ada, ASK, bot=None, schedule={"every": "hour", "input": "now"})
    assert got["schedule_summary"] == "Every hour" and got["next_run_at"]
    await _due(engine, ada)
    assert await tend.tend(engine, Hub(redis), BOTS, 60, None, bots=served.app.state.bots)
    await served.settled()
    (run,) = (await served.http.get("/v1/programs/mail-round/runs", headers=ada.headers)).json()["runs"]
    assert (run["trigger"], run["status"], run["question"]["question"]) == ("schedule", "needs_input", "Go now?")
    assert (await trail(served, ada, run["id"]))[0][:2] == ("started", "")
    await _due(engine, ada)
    with logged("glyphh.programs") as said:
        assert await due.fire(served.app.state.bots.programs) == 0  # its last run still waits: skipped, and said
    assert any("skipped: Mail Round is already running" in line.getMessage() for line in said), said
    off = await served.http.patch("/v1/programs/mail-round", json={"schedule": {"every": "off"}}, headers=ada.headers)
    assert off.json()["next_run_at"] is None and await due.fire(served.app.state.bots.programs) == 0


async def test_a_templates_program_is_installed_with_its_bot(served: Served, ana: Person) -> None:
    await linked(served, ana, "github", "slack")
    any_component(served)
    bot = await installed(served, ana, "pr-review-digest")
    (program,) = (await served.http.get("/v1/programs", headers=ana.headers)).json()["programs"]
    assert (program["bot"], program["template"], program["problems"]) == (bot["slug"], "pr-review-digest", [])
    assert [s["id"] for s in program["flow"]] == ["digest", "approve", "post"]
    waits = await ran(served, ana, program["slug"], "")
    assert waits["question"]["question"].startswith("Post this digest to you in Slack?\n\nHello!")
    done = await answered(served, ana, waits["id"], "Skip")
    assert done["status"] == "done" and "post" not in done["outputs"]


async def test_tools_are_found_and_added_to_a_bot(served: Served, ana: Person) -> None:
    bot = await made_bot(served, ana, connections=[], spec={})
    gmail = (await linked(served, ana, "gmail"))["gmail"]["id"]
    found = (await served.http.get("/v1/tools/search?q=email", headers=ana.headers)).json()["tools"]
    assert [(t["key"], t["app"], t["read_only"], t["added"]) for t in found] == [
        ("gmail-send-email", "Gmail", False, False),
        ("gmail-find-email", "Gmail", True, False),
    ]
    built = (await served.http.get("/v1/tools/search?q=applications", headers=ana.headers)).json()["tools"]
    assert [(t["key"], t["app"], t["connection_id"]) for t in built] == [("inbox_applications", "Glyphh", None)]
    add = {"connection_id": gmail, "tool": "gmail-find-email"}
    path = f"/v1/bots/{bot['slug']}/tools"
    assert (await served.http.post(path, json=add, headers=ana.headers)).status_code == 204
    assert (await served.http.post(path, json={**add, "tool": "gmail-send-email"}, headers=ana.headers)).is_success
    assert (await served.http.post(path, json={"tool": "inbox_applications"}, headers=ana.headers)).is_success
    has = (await served.http.get(f"/v1/tools/search?bot={bot['slug']}", headers=ana.headers)).json()["tools"]
    assert [t["key"] for t in has if t["added"]] == ["inbox_applications", "gmail-send-email", "gmail-find-email"]
    shown = (await served.http.get(f"/v1/bots/{bot['slug']}", headers=ana.headers)).json()
    assert shown["connections"][0]["tools"] == ["gmail-find-email", "gmail-send-email"]
    await made(served, ana, [FIND_STEP])  # and a program's step uses it at once
    assert (await ran(served, ana))["status"] == "done"
    for body, status in [({"tool": "nope"}, 422), ({**add, "tool": "gmail-nope"}, 422),
                         ({**add, "connection_id": "00000000-0000-0000-0000-000000000000"}, 404)]:  # fmt: skip
        assert (await served.http.post(path, json=body, headers=ana.headers)).status_code == status


async def test_the_runs_a_restart_cut_off_are_failed(served: Served, ana: Person, engine: AsyncEngine) -> None:
    await made(served, ana, ASK, bot=None)
    waits = await ran(served, ana)
    async with engine.begin() as conn:
        await conn.execute(update(ProgramRun).where(ProgramRun.id == waits["id"]).values(status="running"))
    assert await served.app.state.bots.recover() == 1
    cut = await run_of(served, ana, waits["id"])
    assert (cut["status"], cut["error"]) == ("failed", "The server restarted while it ran: run it again.")
    assert (await trail(served, ana, waits["id"]))[-1][0] == "failed"
    async with engine.connect() as conn:
        mine = select(ProgramRun.finished_at).where(ProgramRun.id == waits["id"])
        assert (await conn.execute(mine)).scalar_one() is not None
