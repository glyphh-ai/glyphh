"""The orchestrator's hold on the crew, and its own Ada key (docs/specs/bot-agent-loop.md, 8): it starts a run of the
crew on its latest workspace, reads how that run stands and stops it, saying plainly when there is no workspace, no
run, or the crew cannot go; and, made with no Ada key (nothing that makes it can make one), it gets one the first
time it decides."""

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Bot, Org, RuntimeKey
from tests.bots.agents import play
from tests.bots.conftest import DECIDE, Served, inbox, ran
from tests.bots.fakes import MAIL
from tests.db.helpers import Person, person
from tests.projects.helpers import crew, faked, project, say, use

ORCH: str = "orchestrator"
START: tuple[str, dict[str, Any]] = ("crew_start", {"task": "Make the home page"})
NO_CREW: str = "The crew has no workspace yet: the person chooses a repository for it on the Bots screen first."
GATE: str = "bot-orchestrator-gate-worth"


async def on_team(engine: AsyncEngine, who: Person) -> None:
    """Team's calls a second: a faked go takes no time, and Free's five would refuse a test's sixth."""
    team = await person(engine, "Team")
    async with engine.begin() as conn:
        plan = (await conn.execute(select(Org.plan_version_id).where(Org.id == team.org_id))).scalar_one()
        await conn.execute(update(Org).where(Org.id == who.org_id).values(plan_version_id=plan))


async def calls(s: Served, who: Person, *made: tuple[str, dict[str, Any]]) -> list[tuple[str, Any]]:
    """What each of the orchestrator's calls came to, in one run of it."""
    go = play(*made)
    s.agent.script = [go]
    run = await ran(s, who, ORCH, "The crew")
    assert run["status"] == "done", run
    return [(h.kind, h.value) for h in go.heard]  # type: ignore[attr-defined]


async def test_with_no_workspace_or_no_run_it_says_so(served: Served, ana: Person, engine: AsyncEngine) -> None:
    got = await calls(served, ana, START, ("crew_status", {}), ("crew_stop", {}))
    assert got == [("error", NO_CREW)] * 3
    faked(served)
    ada, bots = await crew(served, engine, key=False)  # she has not signed in with GitHub: her crew cannot go
    await project(served, ada, bots)
    got = await calls(served, ada, START, ("crew_status", {}), ("crew_stop", {}))
    assert got[0][0] == "error" and got[0][1].startswith("The crew could not start: ") and "GitHub" in got[0][1]
    assert got[1:] == [("error", "The crew has not run yet.")] * 2


async def test_it_starts_the_crew_reads_how_it_stands_and_stops_it(served: Served, engine: AsyncEngine) -> None:
    _, claude = faked(served)
    ada, bots = await crew(served, engine)
    await on_team(engine, ada)
    await project(served, ada, bots, name="Old site", repo_url="https://github.com/acme/old")
    await project(served, ada, bots)  # the latest workspace: the crew's
    claude.then(use("write_file", path="index.html", content="<h1>Site</h1>\n"), say("Made the home page."))
    got = await calls(served, ada, START)
    assert got == [("result", {"workspace": "Site crew", "status": "running", "task": "Make the home page"})]
    runs = (await served.http.get("/v1/projects/site-crew/runs", headers=ada.headers)).json()["runs"]
    assert [(r["status"], r["task"]) for r in runs] == [("needs_input", "Make the home page")]  # its pull request waits
    got = await calls(
        served, ada, ("crew_status", {}), START, ("crew_stop", {}), ("crew_status", {}), ("crew_stop", {})
    )
    stands, again, stopped, after, twice = got
    assert stands == ("result", {"workspace": "Site crew", "status": "needs_input", "task": runs[0]["task"], "why": ""})
    assert again[0] == "error" and again[1].startswith("The crew could not start: ")  # one live run a project
    assert stopped == ("result", {"workspace": "Site crew", "status": "stopped"})
    assert after[1] == {"workspace": "Site crew", "status": "failed", "task": runs[0]["task"], "why": "cancelled"}
    assert twice == ("error", "That project run has ended.")
    ended = (await served.http.get(f"/v1/project-runs/{runs[0]['id']}", headers=ada.headers)).json()
    assert (ended["status"], ended["error"]) == ("failed", "cancelled")


async def test_its_ada_key_is_made_the_first_time_it_decides(served: Served, ana: Person, engine: AsyncEngine) -> None:
    async def kept() -> tuple[str, int]:
        async with engine.begin() as conn:
            sealed = (await conn.scalars(select(Bot.ada_key).where(Bot.org_id == ana.org_id, Bot.role == ORCH))).one()
            keys = select(func.count()).select_from(RuntimeKey).where(RuntimeKey.name == "bot orchestrator")
            return str(sealed), int((await conn.execute(keys.where(RuntimeKey.user_id == ana.user_id))).scalar_one())

    assert await kept() == ("", 0)  # made with the org, with no key
    res = await served.http.patch(f"/v1/bots/{ORCH}", json={"spec": inbox()}, headers=ana.headers)
    assert res.status_code == 200 and res.json()["gate_models"][0] == GATE
    assert await kept() == ("", 0)  # and none until it is needed
    served.ada.cases[GATE].append(({}, "skip"))
    served.ada.rule[GATE] = lambda case: ("skip", 0.95)
    for _ in range(2):
        go = play((DECIDE, {"decision": "worth", "items": MAIL}), text="Nothing to answer.")
        served.agent.script = [go]
        run = await ran(served, ana, ORCH, "Anything worth answering?")
        assert run["status"] == "done", run
        assert [r["outcome"] for r in go.heard[0].value] == ["skip", "skip"]  # type: ignore[attr-defined]
    sealed, made = await kept()
    assert sealed and made == 1  # one key, as the org's admin, kept sealed and used again
    assert len(set(served.ada.keys)) == 1 and served.ada.keys[0].startswith("glyphh_ak_")
