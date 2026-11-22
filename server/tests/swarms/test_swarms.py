"""The org's swarms (docs/specs/bots.md, 10): a crew of its bots in order on one GitHub repo, run on one of its rrotors;
each turn a call of glyphh_swarm there, its pull request waiting in the approvals queue for a merge or a reject
(review each_turn) or merged as it opens (auto), then Glyphh Bot's DONE rule and the next bot; the org's GitHub
token sent with each call."""

import uuid
from typing import Any

import httpx
import pytest
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.errors import Invalid
from glyphh_server.models import Bot, Rrotor, SwarmRun
from glyphh_server.ops.link import calls
from glyphh_server.ops.link.protocol import Call, Cancel
from glyphh_server.ops.swarms import github
from glyphh_server.ops.swarms.service import Swarms
from tests.bots.conftest import made_bot
from tests.bots.remote import OnRrotor, online, rrotor_fixture  # noqa: F401 (the fixture)
from tests.db.helpers import Person, person
from tests.link import Rt, self_runtime

FINE: dict[str, Any] = {"loop": [{"id": "a", "agent": "Hi"}]}
REPO: str = "https://github.com/acme/site"
TOKEN: str = "github_pat_" + "x" * 30


async def _crew(r: OnRrotor, engine: AsyncEngine, key: bool = True) -> tuple[Person, Rt, list[dict[str, Any]]]:
    ada = await person(engine)
    rt = await online(engine, ada)
    crew = [await made_bot(r.s, ada, name=n, spec=FINE, summary=f"{n} work") for n in ("Ada Cat", "Bo Cat")]
    async with engine.begin() as conn:
        await conn.execute(update(Bot).where(Bot.slug == "ada-cat").values(look={"head": "Round", "eye": "Wide"}))

    async def check(token: str) -> str:
        if token.endswith("bad"):
            raise Invalid("GitHub does not take that token.", reason="token")
        return "acme-bot"

    r.s.app.state.bots.swarms.check_github = check
    if key:
        res = await r.s.http.put("/v1/github-key", json={"token": TOKEN}, headers=ada.headers)
        assert res.status_code == 200 and res.json()["login"] == "acme-bot" and res.json()["hint"] == "xxxx"
    return ada, rt, crew


def _body(rt: Rt, crew: list[dict[str, Any]], **over: Any) -> dict[str, Any]:
    return {"name": "Site crew", "repo_url": REPO, "members": [b["id"] for b in crew], "runs_on": str(rt.id), **over}


async def _swarm(r: OnRrotor, who: Person, rt: Rt, crew: list[dict[str, Any]], **over: Any) -> dict[str, Any]:
    res = await r.s.http.post("/v1/swarms", json=_body(rt, crew, **over), headers=who.headers)
    assert res.status_code == 201, res.text
    return dict(res.json())


async def _start(r: OnRrotor, who: Person, task: str = "Make the home page") -> httpx.Response:
    return await r.s.http.post("/v1/swarms/site-crew/runs", json={"task": task}, headers=who.headers)


def _turned(status: str = "open", said: str = "Wrote the page.", n: int = 7) -> dict[str, Any]:
    data = {"status": status, "said": said, "title": f"turn {n}", "files": [{"path": "a.html", "added": 3}]}
    if status == "open":
        data |= {"pr_url": f"{REPO}/pull/{n}", "number": n, "head_sha": "abc"}
    return {"status": "done", "data": data, "step": None, "prompt": None}


async def _run(r: OnRrotor, who: Person, run_id: Any) -> dict[str, Any]:
    return dict((await r.s.http.get(f"/v1/swarm-runs/{run_id}", headers=who.headers)).json())


async def test_a_swarm_is_made_read_changed_and_deleted(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, crew = await _crew(on_rrotor, engine)
    made = await _swarm(on_rrotor, ada, rt, crew, repo_url=REPO + "/")
    assert made["slug"] == "site-crew" and made["repo_url"] == REPO and made["base_branch"] == "main"
    assert [m["slug"] for m in made["members"]] == ["ada-cat", "bo-cat"] and made["review"] == "each_turn"
    post = on_rrotor.s.http.post
    for body, status, reason in (
        (_body(rt, crew), 409, None),
        (_body(rt, crew, name="B", members=[crew[0]["id"]] * 2), 422, "members"),
        (_body(rt, crew, name="C", members=[str(uuid.uuid4())]), 404, None),
        (_body(rt, crew, name="D", base_branch="a..b"), 422, None),
        (_body(rt, crew, name="E", repo_url="https://gitlab.com/a/b"), 422, None),
    ):
        res = await post("/v1/swarms", json=body, headers=ada.headers)
        assert res.status_code == status, res.text
        assert reason is None or res.json()["error"]["reason"] == reason
    theirs = await self_runtime(engine, await person(engine), "https://rrotor.other.test")
    res = await post("/v1/swarms", json=_body(theirs, crew, name="F"), headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "runs_on"
    patch = {"name": "The crew", "members": [crew[1]["id"]], "repo_url": REPO + "2/", "review": "auto", "rounds": 2}
    patch["base_branch"] = "release/1.2"
    res = await on_rrotor.s.http.patch(
        "/v1/swarms/site-crew", json={**patch, "runs_on": str(rt.id)}, headers=ada.headers
    )
    changed = res.json()
    assert changed["name"] == "The crew" and changed["slug"] == "site-crew" and changed["repo_url"] == REPO + "2"
    assert changed["base_branch"] == "release/1.2"
    assert [m["slug"] for m in changed["members"]] == ["bo-cat"] and (changed["review"], changed["rounds"]) == (
        "auto",
        2,
    )
    assert [s["slug"] for s in (await on_rrotor.s.http.get("/v1/swarms", headers=ada.headers)).json()["swarms"]] == [
        "site-crew"
    ]
    assert (await on_rrotor.s.http.delete("/v1/swarms/site-crew", headers=ada.headers)).status_code == 204
    assert (await on_rrotor.s.http.get("/v1/swarms/site-crew", headers=ada.headers)).status_code == 404


async def test_the_orgs_github_token_is_tried_kept_sealed_and_removed(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, _, _ = await _crew(on_rrotor, engine, key=False)
    shown = (await on_rrotor.s.http.get("/v1/github-key", headers=ada.headers)).json()
    assert shown == {"set": False, "hint": "", "login": "", "set_at": None}
    bad = await on_rrotor.s.http.put("/v1/github-key", json={"token": TOKEN + "bad"}, headers=ada.headers)
    assert bad.status_code == 422 and bad.json()["error"]["reason"] == "token"
    await on_rrotor.s.http.put("/v1/github-key", json={"token": TOKEN}, headers=ada.headers)
    again = await on_rrotor.s.http.put("/v1/github-key", json={"token": TOKEN[:-4] + "abcd"}, headers=ada.headers)
    assert again.json()["set"] is True and again.json()["hint"] == "abcd" and TOKEN not in again.text
    gone = await on_rrotor.s.http.delete("/v1/github-key", headers=ada.headers)
    assert gone.json()["set"] is False


async def test_github_is_asked_who_a_token_is() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.headers["authorization"].endswith("down"):
            raise httpx.ConnectError("no route")
        if request.headers["authorization"].endswith("good"):
            return httpx.Response(200, json={"login": "acme-bot"})
        return httpx.Response(401, json={"message": "Bad credentials"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as http:
        check = github.checker(http)
        assert await check("t-good") == "acme-bot"
        for token, said in (("t-bad", "does not take"), ("t-down", "did not answer")):
            with pytest.raises(Invalid, match=said):
                await check(token)


async def test_a_swarm_run_is_refused_until_it_can_go(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, crew = await _crew(on_rrotor, engine, key=False)
    await _swarm(on_rrotor, ada, rt, crew)
    res = await _start(on_rrotor, ada)
    assert res.status_code == 404 and res.json()["error"]["reason"] == "github_key"
    await on_rrotor.s.http.put("/v1/github-key", json={"token": TOKEN}, headers=ada.headers)
    async with engine.begin() as conn:
        await conn.execute(delete(Bot).where(Bot.org_id == ada.org_id))
    res = await _start(on_rrotor, ada)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "members"
    async with engine.begin() as conn:
        await conn.execute(update(Rrotor).where(Rrotor.id == rt.id).values(state="stopped"))
    res = await _start(on_rrotor, ada)
    assert res.status_code == 409 and res.json()["error"]["reason"] == "rrotor_offline"


async def test_each_turn_waits_for_a_merge_or_a_reject(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, crew = await _crew(on_rrotor, engine)
    await _swarm(on_rrotor, ada, rt, crew)
    res = await _start(on_rrotor, ada)
    assert res.status_code == 202, res.text
    run = res.json()
    assert run["status"] == "running" and run["runs_on"] == str(rt.id) and run["turns"][0]["status"] == "running"
    to, first = on_rrotor.hub.sent[-1]
    assert to == rt.id and isinstance(first, Call) and (first.program, first.function) == ("glyphh_swarm", "turn")
    given = first.inputs
    assert given["repo"] == "acme/site" and given["github_token"] == TOKEN and given["base"] == "main"
    assert given["branch"].startswith("turn-1-ada-cat-") and given["bot_name"] == "Ada Cat"
    assert (
        "your own look: round, wide" in given["persona"]
        and "CREW TASK from the person: Make the home" in given["prompt"]
    )
    assert (await _start(on_rrotor, ada)).status_code == 409  # one live run at a time
    await on_rrotor.landed(rt, ada, first.run_id, _turned())
    waiting = await _run(on_rrotor, ada, run["id"])
    assert waiting["status"] == "needs_input" and waiting["turns"][0]["status"] == "open"
    assert waiting["turns"][0]["number"] == 7 and waiting["turns"][0]["files"] == [{"path": "a.html", "added": 3}]
    queue = (await on_rrotor.s.http.get("/v1/bot-approvals", headers=ada.headers)).json()["runs"]
    assert [(q["kind"], q["swarm_slug"], q["question"]["question"]) for q in queue] == [
        ("swarm", "site-crew", "Merge PR #7 by Ada Cat?")
    ]
    assert queue[0]["question"]["options"] == ["merge", "reject"] and queue[0]["data"]["pr_url"] == f"{REPO}/pull/7"
    answer = on_rrotor.s.http.post
    res = await answer(f"/v1/swarm-runs/{run['id']}/answer", json={"answer": "merge"}, headers=ada.headers)
    assert res.status_code == 202 and res.json()["turns"][0]["status"] == "merging"
    merge = on_rrotor.hub.last()
    assert merge.function == "merge" and merge.inputs["pr_url"] == f"{REPO}/pull/7"
    assert merge.inputs["github_token"] == TOKEN
    seq = await on_rrotor.landed(rt, ada, merge.run_id, {"status": "done", "data": {"status": "merged"}})
    await on_rrotor.landed(rt, ada, merge.run_id, {"status": "done", "data": {"status": "merged"}}, seq=seq)  # replay
    second = on_rrotor.hub.last()
    assert second.function == "turn" and second.inputs["branch"].startswith("turn-2-bo-cat-")
    assert "Ada Cat: Wrote the page." in second.inputs["prompt"] and "This is the last turn" in second.inputs["prompt"]
    await on_rrotor.landed(rt, ada, second.run_id, _turned(said="Tests pass.\nDONE", n=8))
    no = await answer(f"/v1/swarm-runs/{run['id']}/answer", json={"answer": "reject"}, headers=ada.headers)
    res = await answer(f"/v1/swarm-runs/{run['id']}/answer", json={"answer": "merge"}, headers=ada.headers)
    assert no.status_code == 202 and res.status_code == 409  # it no longer waits
    assert on_rrotor.hub.last().function == "reject"
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, {"status": "done", "data": {"status": "rejected"}})
    ended = await _run(on_rrotor, ada, run["id"])
    assert ended["status"] == "done" and [t["status"] for t in ended["turns"]] == ["merged", "rejected"]
    assert ended["turns"][1]["done"] is True and ended["finished_at"]
    assert (await on_rrotor.s.http.post(f"/v1/swarm-runs/{run['id']}/cancel", headers=ada.headers)).status_code == 409
    assert (await on_rrotor.s.http.get(f"/v1/swarm-runs/{uuid.uuid4()}", headers=ada.headers)).status_code == 404
    listed = (await on_rrotor.s.http.get("/v1/swarms/site-crew/runs", headers=ada.headers)).json()["runs"]
    assert [r["id"] for r in listed] == [run["id"]]


async def test_auto_merges_each_and_the_crew_ends_when_both_say_done(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, crew = await _crew(on_rrotor, engine)
    await _swarm(on_rrotor, ada, rt, crew, review="auto", rounds=3)
    run = (await _start(on_rrotor, ada)).json()
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, _turned())
    merge = on_rrotor.hub.last()
    assert merge.function == "merge" and (await _run(on_rrotor, ada, run["id"]))["status"] == "running"
    conflict = {"status": "done", "data": {"status": "conflict", "reason": "a.html changed on main"}}
    await on_rrotor.landed(rt, ada, merge.run_id, conflict)
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, _turned("unchanged", said="Looks right.\nDONE"))
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, _turned("unchanged", said="DONE"))
    ended = await _run(on_rrotor, ada, run["id"])
    assert ended["status"] == "done" and [t["status"] for t in ended["turns"]] == ["conflict", "unchanged", "unchanged"]
    assert ended["turns"][0]["error"] == "a.html changed on main" and ended["turns"][1]["pr_url"] is None


async def test_a_swarm_run_that_cannot_go_on_ends_saying_why(
    on_rrotor: OnRrotor, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    ada, rt, crew = await _crew(on_rrotor, engine)
    await _swarm(on_rrotor, ada, rt, crew)
    run = (await _start(on_rrotor, ada)).json()
    failed = {"status": "failed", "data": {"reason": "the clone failed", "code": "E_GIT"}, "step": "turn"}
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, failed)
    ended = await _run(on_rrotor, ada, run["id"])
    assert ended["status"] == "failed" and ended["error"] == "Ada Cat's turn 1 failed: the clone failed"
    on_rrotor.hub.up = False
    run = (await _start(on_rrotor, ada)).json()
    assert run["status"] == "failed" and "The swarm's rrotor is not linked" in run["error"]
    on_rrotor.hub.up = True
    monkeypatch.setattr(calls, "LINK_MAX", 100)
    run = (await _start(on_rrotor, ada)).json()
    assert run["status"] == "failed" and "The turn is" in run["error"] and run["turns"][0]["status"] == "failed"
    monkeypatch.undo()
    run = (await _start(on_rrotor, ada)).json()
    other = await online(engine, ada)
    await on_rrotor.landed(other, ada, on_rrotor.hub.last().run_id, _turned())  # not its rrotor: skipped
    assert (await _run(on_rrotor, ada, run["id"]))["status"] == "running"

    async def broken(*_: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(Swarms, "_took", broken)
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, _turned())
    ended = await _run(on_rrotor, ada, run["id"])
    assert ended["status"] == "failed" and ended["error"] == "The rrotor's result could not be kept: boom"
    monkeypatch.undo()
    run = (await _start(on_rrotor, ada)).json()
    async with engine.begin() as conn:
        await conn.execute(delete(Bot).where(Bot.slug == "bo-cat", Bot.org_id == ada.org_id))
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, _turned("unchanged"))
    ended = await _run(on_rrotor, ada, run["id"])
    assert ended["status"] == "failed" and ended["error"].startswith("A bot of the crew was deleted")


async def test_a_swarm_run_is_cancelled_and_its_turn_stopped(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, crew = await _crew(on_rrotor, engine)
    await _swarm(on_rrotor, ada, rt, crew)
    first = (await _start(on_rrotor, ada)).json()
    out = on_rrotor.hub.last()
    res = await on_rrotor.s.http.post(f"/v1/swarm-runs/{first['id']}/cancel", headers=ada.headers)
    assert res.status_code == 200 and res.json()["status"] == "failed" and res.json()["error"] == "cancelled"
    assert res.json()["turns"][0]["status"] == "cancelled"
    assert isinstance(on_rrotor.hub.last(), Cancel) and on_rrotor.hub.last().run_id == out.run_id
    run = (await _start(on_rrotor, ada)).json()
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, _turned())
    told = len(on_rrotor.hub.sent)
    res = await on_rrotor.s.http.post(f"/v1/swarm-runs/{run['id']}/cancel", headers=ada.headers)
    assert res.json()["turns"][0]["status"] == "open" and len(on_rrotor.hub.sent) == told  # its pull request stays
    async with engine.begin() as conn:  # waiting with no pull request open: not in the queue
        await conn.execute(update(SwarmRun).where(SwarmRun.id == uuid.UUID(first["id"])).values(status="needs_input"))
    assert (await on_rrotor.s.http.get("/v1/bot-approvals", headers=ada.headers)).json()["runs"] == []
