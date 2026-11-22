"""The org's projects (docs/specs/bots.md, 10): a crew of its bots, in no order, on one GitHub repo and a set of
instructions; made, changed and deleted; and a run on one of the org's rrotors: each step a call of glyphh_swarm
there (a turn, the orchestrator's pick, a merge or a reject) with a GitHub token minted for it, wait your turn or the
orchestrator's choice, until the crew is done or a safety cap is reached. The old swarm paths still answer."""

import uuid
from typing import Any

import pytest
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Bot, ProjectRun, Rrotor
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.protocol import Call, Cancel
from glyphh_server.ops.projects.results import Results
from tests.bots.remote import OnRrotor, online, rrotor_fixture  # noqa: F401 (the fixture)
from tests.db.helpers import person
from tests.link import self_runtime
from tests.projects.helpers import (
    INSTALLATION,
    REPO,
    answer,
    body,
    github_of,
    picked,
    project,
    run_of,
    signs_in_with_github,
    start,
    turned,
)
from tests.projects.helpers import crew_on_rrotor as _on


async def test_a_project_is_made_read_changed_and_deleted(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    r = on_rrotor
    ada, rt, bots = await _on(r, engine)
    made = await project(r.s, ada, bots, repo_url=REPO + "/")
    assert made["slug"] == "site-crew" and made["repo_url"] == REPO and made["base_branch"] == "main"
    assert sorted(m["slug"] for m in made["members"]) == ["ada-cat", "bo-cat"]
    assert (made["review"], made["turn_mode"], made["runs_on"], made["orchestrator"]) == (
        "each_turn",
        "wait",
        None,
        None,
    )
    assert (made["instructions"], made["instructions_path"], made["max_turns"]) == ("", "PROJECT.md", 30)
    assert made["max_spend_cents"] is None and made["narrate"] is False
    post = r.s.http.post
    for given, status, reason in (
        (body(bots), 409, None),
        (body(bots, name="B", members=[bots[0]["id"]] * 2), 422, "members"),
        (body(bots, name="C", members=[str(uuid.uuid4())]), 404, None),
        (body(bots, name="D", base_branch="a..b"), 422, None),
        (body(bots, name="E", repo_url="https://gitlab.com/a/b"), 422, None),
        (body(bots, name="F", instructions_path="../etc/passwd"), 422, None),
        (body(bots, name="G", orchestrator=str(uuid.uuid4())), 422, "orchestrator"),
        (body(bots, name="H", rounds=2), 422, None),
    ):
        res = await post("/v1/projects", json=given, headers=ada.headers)
        assert res.status_code == status, res.text
        assert reason is None or res.json()["error"]["reason"] == reason
    theirs = await self_runtime(engine, await person(engine), "https://rrotor.other.test")
    res = await post("/v1/projects", json=body(bots, name="I", runs_on=str(theirs.id)), headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "runs_on"
    patch = {"name": "The crew", "repo_url": REPO + "2/", "review": "end", "base_branch": "release/1.2"}
    patch |= {"turn_mode": "orchestrator", "orchestrator": bots[1]["id"], "runs_on": str(rt.id), "narrate": True}
    patch |= {"instructions": "Ship it.", "instructions_path": "docs/PLAN.md", "max_turns": 5, "max_spend_cents": 250}
    changed = (await r.s.http.patch("/v1/projects/site-crew", json=patch, headers=ada.headers)).json()
    assert changed["slug"] == "site-crew" and changed["repo_url"] == REPO + "2"
    assert {k: changed[k] for k in patch if k not in ("repo_url",)} == {
        k: v for k, v in patch.items() if k != "repo_url"
    }
    gone = {"members": [bots[0]["id"]]}
    res = await r.s.http.patch("/v1/projects/site-crew", json=gone, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "orchestrator"  # its orchestrator left the crew
    cleared = {**gone, "orchestrator": None, "runs_on": None, "max_spend_cents": None, "name": None}
    back = (await r.s.http.patch("/v1/projects/site-crew", json=cleared, headers=ada.headers)).json()
    assert (back["orchestrator"], back["runs_on"], back["max_spend_cents"], back["name"]) == (
        None,
        None,
        None,
        "The crew",
    )
    assert [m["slug"] for m in back["members"]] == ["ada-cat"]
    listed = (await r.s.http.get("/v1/projects", headers=ada.headers)).json()["projects"]
    assert [p["slug"] for p in listed] == ["site-crew"]
    assert (await r.s.http.delete("/v1/projects/site-crew", headers=ada.headers)).status_code == 204
    assert (await r.s.http.get("/v1/projects/site-crew", headers=ada.headers)).status_code == 404


async def test_a_project_still_answers_at_a_swarms_paths(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    r = on_rrotor
    ada, rt, bots = await _on(r, engine)
    old = body(bots, runs_on=str(rt.id), rounds=3, review="auto")
    res = await r.s.http.post("/v1/swarms", json=old, headers=ada.headers)
    assert res.status_code == 201 and res.json()["review"] == "end" and "rounds" not in res.json()
    bad = await r.s.http.post("/v1/swarms", json={"name": "x"}, headers=ada.headers)
    assert bad.status_code == 422 and bad.json()["error"]["reason"] == "body"
    assert any(p.startswith("repo_url:") for p in bad.json()["error"]["problems"])
    listed = (await r.s.http.get("/v1/swarms", headers=ada.headers)).json()
    assert listed["swarms"] == listed["projects"] and listed["swarms"][0]["slug"] == "site-crew"
    res = await r.s.http.patch("/v1/swarms/site-crew", json={"rounds": 1, "review": "each_turn"}, headers=ada.headers)
    assert res.status_code == 200 and res.json()["review"] == "each_turn"
    assert (await r.s.http.get("/v1/swarms/site-crew", headers=ada.headers)).json()["slug"] == "site-crew"
    run = (await r.s.http.post("/v1/swarms/site-crew/runs", json={"task": "Go"}, headers=ada.headers)).json()
    assert run["status"] == "running" and run["project_slug"] == "site-crew"
    assert (await r.s.http.get("/v1/swarms/site-crew/runs", headers=ada.headers)).json()["runs"][0]["id"] == run["id"]
    assert (await r.s.http.get(f"/v1/swarm-runs/{run['id']}", headers=ada.headers)).status_code == 200
    await r.landed(rt, ada, r.hub.last().run_id, turned())
    res = await r.s.http.post(f"/v1/swarm-runs/{run['id']}/answer", json={"answer": "merge"}, headers=ada.headers)
    assert res.status_code == 202
    assert (await r.s.http.post(f"/v1/swarm-runs/{run['id']}/cancel", headers=ada.headers)).status_code == 200
    assert (await r.s.http.delete("/v1/swarms/site-crew", headers=ada.headers)).status_code == 204


async def test_the_pasted_github_token_is_gone(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, _, _ = await _on(on_rrotor, engine)
    for method in ("GET", "PUT", "DELETE"):
        res = await on_rrotor.s.http.request(method, "/v1/github-key", headers=ada.headers)
        assert res.status_code == 404, res.text


async def test_a_run_is_refused_until_it_can_go(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    r = on_rrotor
    ada, rt, bots = await _on(r, engine, key=False)
    made = await project(r.s, ada, bots, runs_on=str(rt.id))
    assert made["github_connected"] is False
    res = await start(r.s, ada)
    said = res.json()["error"]
    assert res.status_code == 404 and said["reason"] == "github_app_missing", res.text
    assert (
        said["install_url"] == "https://github.com/apps/glyphh-test/installations/new"
        and "acme/site" in said["message"]
    )
    gh = github_of(r.s)
    gh.install("acme/site", INSTALLATION)
    res = await start(r.s, ada)
    assert res.status_code == 403 and res.json()["error"]["reason"] == "github_not_linked", res.text
    account = await signs_in_with_github(engine, ada, "ada-gh")
    gh.logins |= dict([account])
    res = await start(r.s, ada)
    assert res.status_code == 403 and res.json()["error"]["reason"] == "github_no_write", res.text
    gh.install("acme/site", INSTALLATION, account)
    async with engine.begin() as conn:
        await conn.execute(delete(Bot).where(Bot.org_id == ada.org_id))
    res = await start(r.s, ada)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "members"
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(state="stopped"))
    res = await start(r.s, ada)
    assert res.status_code == 409 and res.json()["error"]["reason"] == "rrotor_offline"


async def test_wait_your_turn_on_a_rrotor_each_pull_request_waits(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    r = on_rrotor
    ada, rt, bots = await _on(r, engine)
    await project(r.s, ada, bots, runs_on=str(rt.id), instructions="Ship a landing page.")
    res = await start(r.s, ada)
    assert res.status_code == 202, res.text
    run = res.json()
    assert run["status"] == "running" and run["runs_on"] == str(rt.id) and run["turns"][0]["status"] == "running"
    assert (run["turn_mode"], run["max_turns"], run["work_branch"], run["ended"]) == ("wait", 30, None, "")
    to, first = r.hub.sent[-1]
    assert to == rt.id and isinstance(first, Call) and (first.program, first.function) == ("glyphh_swarm", "turn")
    given = first.inputs
    assert given["repo"] == "acme/site" and given["base"] == "main"
    minted = github_of(r.s).tokens[given["github_token"]]  # the turn's own token: this repo, and no more than it needs
    assert minted["installation"] == INSTALLATION and minted["repos"] == ["acme/site"]
    assert minted["permissions"] == {"contents": "write", "pull_requests": "write", "metadata": "read"}
    shown = (await r.s.http.get("/v1/projects/site-crew", headers=ada.headers)).json()
    assert shown["github_connected"] is True
    assert given["branch"].startswith("turn-1-ada-cat-") and given["bot_name"] == "Ada Cat"
    assert "your own look: round, wide" in given["persona"]
    assert given["prompt"].startswith("PROJECT INSTRUCTIONS:\nShip a landing page.\n\nThe repo may hold more")
    assert (
        "TASK from the person: Make the home page" in given["prompt"]
        and 'You are on git branch "turn-1' in given["prompt"]
    )
    assert (await start(r.s, ada)).status_code == 409  # one live run at a time
    await r.landed(rt, ada, first.run_id, turned())
    waiting = await run_of(r.s, ada, run["id"])
    assert waiting["status"] == "needs_input" and waiting["turns"][0]["status"] == "open"
    mine = waiting["turns"][0]
    assert mine["number"] == 7 and mine["files"] == [{"path": "a.html", "added": 3}] and mine["picked_by"] == "wait"
    assert (mine["input_tokens"], mine["output_tokens"], mine["cost_micros"]) == (1000, 100, 6000)
    assert (waiting["input_tokens"], waiting["cost_micros"]) == (1000, 6000)
    queue = (await r.s.http.get("/v1/bot-approvals", headers=ada.headers)).json()["runs"]
    assert [(q["kind"], q["project_slug"], q["question"]["question"]) for q in queue] == [
        ("project", "site-crew", "Merge PR #7 by Ada Cat?")
    ]
    assert queue[0]["question"]["options"] == ["merge", "reject"] and queue[0]["data"]["pr_url"] == f"{REPO}/pull/7"
    res = await answer(r.s, ada, run["id"], "merge")
    assert res.status_code == 202 and res.json()["turns"][0]["status"] == "merging"
    merge = r.hub.last()
    assert merge.function == "merge" and merge.inputs["pr_url"] == f"{REPO}/pull/7"
    seq = await r.landed(rt, ada, merge.run_id, {"status": "done", "data": {"status": "merged"}})
    await r.landed(rt, ada, merge.run_id, {"status": "done", "data": {"status": "merged"}}, seq=seq)  # a replay
    second = r.hub.last()
    assert second.function == "turn" and second.inputs["branch"].startswith("turn-2-bo-cat-")
    assert "Ada Cat: Wrote the page." in second.inputs["prompt"]
    await r.landed(rt, ada, second.run_id, turned(said="Tests pass.\nDONE", n=8, usage=None))
    no = await answer(r.s, ada, run["id"], "reject")
    assert no.status_code == 202 and (await answer(r.s, ada, run["id"], "merge")).status_code == 409  # no longer waits
    assert r.hub.last().function == "reject"
    await r.landed(rt, ada, r.hub.last().run_id, {"status": "done", "data": {"status": "rejected"}})
    third = r.hub.last()  # one DONE is not the crew's: the bot that waited longest goes
    assert third.function == "turn" and third.inputs["bot_id"] == "ada-cat"
    await r.landed(rt, ada, third.run_id, turned("unchanged", said="Agreed.\nDONE"))
    ended = await run_of(r.s, ada, run["id"])
    assert (ended["status"], ended["ended"]) == ("done", "done") and ended["finished_at"]
    assert [t["status"] for t in ended["turns"]] == ["merged", "rejected", "unchanged"] and ended["turns"][1]["done"]
    assert (await r.s.http.post(f"/v1/project-runs/{run['id']}/cancel", headers=ada.headers)).status_code == 409
    assert (await r.s.http.get(f"/v1/project-runs/{uuid.uuid4()}", headers=ada.headers)).status_code == 404
    listed = (await r.s.http.get("/v1/projects/site-crew/runs", headers=ada.headers)).json()["runs"]
    assert [x["id"] for x in listed] == [run["id"]]


async def test_a_crew_with_nothing_left_to_do_or_a_cap_ends_the_run(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    r = on_rrotor
    ada, rt, bots = await _on(r, engine)
    await project(r.s, ada, bots, runs_on=str(rt.id))
    run = (await start(r.s, ada, "")).json()
    assert run["task"] == "" and "TASK from the person" not in r.hub.last().inputs["prompt"]
    await r.landed(rt, ada, r.hub.last().run_id, turned("unchanged", said="Nothing for me.\nPASS"))
    assert r.hub.last().inputs["bot_id"] == "bo-cat"
    await r.landed(rt, ada, r.hub.last().run_id, turned("unchanged", said="PASS"))
    ended = await run_of(r.s, ada, run["id"])
    assert (ended["status"], ended["ended"]) == ("done", "done") and len(ended["turns"]) == 2
    await r.s.http.patch("/v1/projects/site-crew", json={"max_turns": 1}, headers=ada.headers)
    run = (await start(r.s, ada)).json()
    await r.landed(rt, ada, r.hub.last().run_id, turned())
    await answer(r.s, ada, run["id"], "merge")
    conflict = {"status": "done", "data": {"status": "conflict", "reason": "a.html changed on main"}}
    await r.landed(rt, ada, r.hub.last().run_id, conflict)
    capped = await run_of(r.s, ada, run["id"])
    assert (capped["status"], capped["ended"]) == ("done", "max_turns")
    assert capped["turns"][0]["status"] == "conflict" and capped["turns"][0]["error"] == "a.html changed on main"
    await r.s.http.patch("/v1/projects/site-crew", json={"max_turns": 9, "max_spend_cents": 1}, headers=ada.headers)
    run = (await start(r.s, ada)).json()
    big = {"input_tokens": 3_000_000, "output_tokens": 0}  # 3M tokens of Opus input: $12
    await r.landed(rt, ada, r.hub.last().run_id, turned("unchanged", said="Read it all.", usage=big))
    spent = await run_of(r.s, ada, run["id"])
    assert (spent["status"], spent["ended"], spent["max_spend_cents"]) == ("done", "max_spend", 1)


async def test_an_orchestrator_on_a_rrotor_picks_who_goes(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    r = on_rrotor
    ada, rt, bots = await _on(r, engine)
    await project(r.s, ada, bots, runs_on=str(rt.id), turn_mode="orchestrator", orchestrator=bots[0]["id"])
    run = (await start(r.s, ada)).json()
    assert (run["turns"][0]["status"], run["turns"][0]["bot_name"], run["turns"][0]["bot_slug"]) == (
        "picking",
        "Orchestrator",
        "",
    )
    pick = r.hub.last()
    assert pick.function == "pick" and set(pick.inputs) == {
        "base",
        "prompt",
        "persona",
        "model",
        "repo",
        "github_token",
    }
    assert "- Ada Cat [ada-cat] (they/them): Ada Cat work" in pick.inputs["prompt"]
    assert "You are this project's orchestrator. Turn 1 is next." in pick.inputs["prompt"]
    assert pick.inputs["persona"].startswith("You are Ada Cat (they/them)")
    await r.landed(rt, ada, pick.run_id, picked('{"next": "bo-cat", "why": "Tests are missing.", "done": false}'))
    turn = r.hub.last()
    assert turn.function == "turn" and turn.inputs["bot_id"] == "bo-cat" and turn.run_id != pick.run_id
    assert "It is your turn, Bo Cat (turn 1). The orchestrator chose you: Tests are missing." in turn.inputs["prompt"]
    going = await run_of(r.s, ada, run["id"])
    mine = going["turns"][0]
    assert (mine["status"], mine["bot_slug"], mine["picked_by"], mine["why"]) == (
        "running",
        "bo-cat",
        "orchestrator",
        "",
    )
    assert (mine["input_tokens"], mine["output_tokens"]) == (500, 50) and len(going["turns"]) == 1
    await r.landed(rt, ada, turn.run_id, turned("unchanged", said="Added tests."))
    await r.landed(rt, ada, r.hub.last().run_id, picked("Somebody, I suppose."))  # names nobody: wait your turn
    assert r.hub.last().inputs["bot_id"] == "ada-cat" and "orchestrator chose" not in r.hub.last().inputs["prompt"]
    assert (await run_of(r.s, ada, run["id"]))["turns"][1]["picked_by"] == "wait"
    await r.landed(rt, ada, r.hub.last().run_id, turned(said="Polished."))
    await answer(r.s, ada, run["id"], "merge")
    await r.landed(rt, ada, r.hub.last().run_id, {"status": "done", "data": {"status": "merged"}})
    await r.landed(rt, ada, r.hub.last().run_id, picked('{"next": "ada-cat", "why": ""}'))
    assert "The orchestrator chose you: It is your turn." in r.hub.last().inputs["prompt"]
    await r.landed(rt, ada, r.hub.last().run_id, turned("unchanged", said="More polish, more to do."))
    await r.landed(rt, ada, r.hub.last().run_id, picked('{"next": null, "why": "All shipped.", "done": true}'))
    ended = await run_of(r.s, ada, run["id"])
    assert (ended["status"], ended["ended"]) == ("done", "orchestrator")
    last = ended["turns"][-1]  # the orchestrator's last word stays on the rrotor
    assert (last["bot_name"], last["status"], last["done"], last["said"]) == ("Orchestrator", "unchanged", True, "")


async def test_an_orchestrator_needs_a_rrotor_that_knows_pick_and_claude_can_be_it(
    on_rrotor: OnRrotor,
    engine: AsyncEngine,
) -> None:
    r = on_rrotor
    ada, rt, bots = await _on(r, engine)
    await project(r.s, ada, bots, runs_on=str(rt.id), turn_mode="orchestrator")
    run = (await start(r.s, ada)).json()
    pick = r.hub.last()
    assert pick.inputs["persona"] == "" and pick.inputs["model"] == "claude-opus-5-5"
    failed = {"status": "failed", "data": {"reason": "glyphh_swarm has no function pick"}}
    await r.landed(rt, ada, pick.run_id, failed)
    ended = await run_of(r.s, ada, run["id"])
    assert ended["status"] == "failed" and ended["error"].startswith(
        "Orchestrator's turn 1 failed: glyphh_swarm has no function pick (an orchestrator needs rrotor 0.6 or later"
    )
    run = (await start(r.s, ada)).json()
    async with engine.begin() as conn:
        await conn.execute(delete(Bot).where(Bot.slug == "bo-cat", Bot.org_id == ada.org_id))
    await r.landed(rt, ada, r.hub.last().run_id, picked('{"next": "bo-cat"}'))
    ended = await run_of(r.s, ada, run["id"])
    assert ended["status"] == "failed" and ended["error"].startswith("A bot of the crew was deleted")


async def test_review_at_the_end_on_a_rrotor(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    r = on_rrotor
    ada, rt, bots = await _on(r, engine)
    repo = r.s.app.state.bots.projects.repo_for("", "")
    await project(r.s, ada, bots, runs_on=str(rt.id), review="end", max_turns=1)
    run = (await start(r.s, ada)).json()
    work = run["work_branch"]
    assert work.startswith("project-site-crew-") and ("branch", work) in repo.asked
    assert r.hub.last().inputs["base"] == work
    await r.landed(rt, ada, r.hub.last().run_id, turned())
    merge = r.hub.last()  # merged as it opens, into the run's own branch
    assert merge.function == "merge" and merge.inputs["pr_url"] == f"{REPO}/pull/7"
    assert (await run_of(r.s, ada, run["id"]))["status"] == "running"
    await r.landed(rt, ada, merge.run_id, {"status": "done", "data": {"status": "merged"}})
    waiting = await run_of(r.s, ada, run["id"])
    assert (waiting["status"], waiting["ended"], waiting["number"]) == ("needs_input", "max_turns", 1)
    assert repo.pulls[1] | {"body": ""} == {
        "head": work,
        "base": "main",
        "title": "Site crew: Make the home page",
        "body": "",
        "state": "open",
    }
    assert repo.pulls[1]["body"] == "The crew's merged turns:\n- #7 turn 7"
    queue = (await r.s.http.get("/v1/bot-approvals", headers=ada.headers)).json()["runs"]
    assert queue[0]["question"]["question"] == "Merge PR #1, the whole run?" and queue[0]["data"]["branch"] == work
    assert queue[0]["bot_slug"] == "" and queue[0]["kind"] == "project"
    done = (await answer(r.s, ada, run["id"], "merge")).json()
    assert (done["status"], done["ended"], done["pr_url"]) == ("done", "max_turns", f"{REPO}/pull/1")
    assert repo.pulls[1]["state"] == "merged" and ("drop", work) in repo.asked


async def test_a_run_that_cannot_go_on_ends_saying_why(
    on_rrotor: OnRrotor,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r = on_rrotor
    ada, rt, bots = await _on(r, engine)
    await project(r.s, ada, bots, runs_on=str(rt.id))
    run = (await start(r.s, ada)).json()
    failed = {"status": "failed", "data": {"reason": "the clone failed", "code": "E_GIT"}, "step": "turn"}
    await r.landed(rt, ada, r.hub.last().run_id, failed)
    ended = await run_of(r.s, ada, run["id"])
    assert ended["status"] == "failed" and ended["error"] == "Ada Cat's turn 1 failed: the clone failed"
    r.hub.up = False
    run = (await start(r.s, ada)).json()
    assert run["status"] == "failed" and "The project's rrotor is not linked" in run["error"]
    r.hub.up = True
    monkeypatch.setattr(calls, "LINK_MAX", 100)
    run = (await start(r.s, ada)).json()
    assert run["status"] == "failed" and "The turn is" in run["error"] and run["turns"][0]["status"] == "failed"
    monkeypatch.undo()
    run = (await start(r.s, ada)).json()
    other = await online(engine, ada)
    await r.landed(other, ada, r.hub.last().run_id, turned())  # not its rrotor: skipped
    assert (await run_of(r.s, ada, run["id"]))["status"] == "running"

    async def broken(*_: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(Results, "_took", broken)
    await r.landed(rt, ada, r.hub.last().run_id, turned())
    ended = await run_of(r.s, ada, run["id"])
    assert ended["status"] == "failed" and ended["error"] == "The step's result could not be kept: boom"
    monkeypatch.undo()
    run = (await start(r.s, ada)).json()
    async with engine.begin() as conn:
        await conn.execute(delete(Bot).where(Bot.slug == "bo-cat", Bot.org_id == ada.org_id))
    await r.landed(rt, ada, r.hub.last().run_id, turned("unchanged"))
    ended = await run_of(r.s, ada, run["id"])
    assert ended["status"] == "failed" and ended["error"].startswith("A bot of the crew was deleted")


async def test_a_run_is_cancelled_and_its_turn_stopped(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    r = on_rrotor
    ada, rt, bots = await _on(r, engine)
    await project(r.s, ada, bots, runs_on=str(rt.id))
    first = (await start(r.s, ada)).json()
    out = r.hub.last()
    res = await r.s.http.post(f"/v1/project-runs/{first['id']}/cancel", headers=ada.headers)
    assert res.status_code == 200 and res.json()["status"] == "failed" and res.json()["error"] == "cancelled"
    assert res.json()["turns"][0]["status"] == "cancelled"
    assert isinstance(r.hub.last(), Cancel) and r.hub.last().run_id == out.run_id
    run = (await start(r.s, ada)).json()
    await r.landed(rt, ada, r.hub.last().run_id, turned())
    told = len(r.hub.sent)
    res = await r.s.http.post(f"/v1/project-runs/{run['id']}/cancel", headers=ada.headers)
    assert res.json()["turns"][0]["status"] == "open" and len(r.hub.sent) == told  # its pull request stays
    async with engine.begin() as conn:  # waiting with no pull request open: not in the queue
        await conn.execute(
            update(ProjectRun).where(ProjectRun.id == uuid.UUID(first["id"])).values(status="needs_input")
        )
    assert (await r.s.http.get("/v1/bot-approvals", headers=ada.headers)).json()["runs"] == []
    assert (await answer(r.s, ada, first["id"], "merge")).status_code == 409
