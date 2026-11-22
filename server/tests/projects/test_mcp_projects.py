"""The connector's project tools: a project made, read, changed, run, its pull request merged from the chat (and shown
in bot_approvals beside the bots' questions), its run cancelled, the project deleted; each still called by the name it
had as a swarm's, never listed; and a bot's run on its rrotor as the bot tools tell it."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.bots.conftest import made_bot
from tests.bots.remote import REMOTE, OnRrotor, online, result, rrotor_fixture  # noqa: F401 (the fixture)
from tests.connector import granted, rpc, tool
from tests.db.helpers import person
from tests.projects.helpers import REPO, crew_on_rrotor, turned

RESOURCE: str = REMOTE.mcp_resource


def _said(got: dict[str, Any]) -> str:
    assert not got.get("isError"), got
    return str(got["content"][0]["text"])


async def test_a_project_is_made_run_and_merged_from_the_chat(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, bots = await crew_on_rrotor(on_rrotor, engine)
    _, auth = await granted(engine, ada, RESOURCE)
    http = on_rrotor.s.http
    assert _said(await tool(http, auth, "projects")) == "The org has no projects yet."
    made = {"name": "Site crew", "repo_url": REPO, "members": [b["id"] for b in bots]}
    said = _said((await rpc(http, auth, "tools/call", name="project_create", arguments=made))["result"])
    assert (
        "Made Site crew (site-crew): https://github.com/acme/site on main, crew Ada Cat, Bo Cat; on Glyphh cloud"
        in said
    )
    assert "wait your turn, review each turn, at most 30 turns" in _said(
        await tool(http, auth, "project", slug="site-crew")
    )
    changed = _said(await tool(http, auth, "project_update", slug="site-crew", runs_on=str(rt.id), review="end"))
    assert f"on rrotor {rt.id}" in changed and "review at the end" in changed
    await tool(http, auth, "project_update", slug="site-crew", review="each_turn")
    assert "site-crew" in _said(await tool(http, auth, "projects"))
    assert _said(await tool(http, auth, "project_runs", slug="site-crew")) == "No runs yet."
    started = await tool(http, auth, "project_run", slug="site-crew", task="Make the home page")
    assert "of site-crew: running. turn 1 Ada Cat: running" in _said(started)
    run_id = started["structuredContent"]["id"]
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, turned())
    queue = _said(await tool(http, auth, "bot_approvals"))
    assert f"Project run {run_id} of site-crew: It asks: Merge PR #7 by Ada Cat? (merge, reject)" in queue
    assert f"turn 1 Ada Cat: open {REPO}/pull/7" in _said(await tool(http, auth, "project_run_get", run_id=run_id))
    assert "merging" in _said(await tool(http, auth, "project_run_answer", run_id=run_id, answer="merge"))
    assert run_id in _said(await tool(http, auth, "project_runs", slug="site-crew"))
    assert _said(await tool(http, auth, "project_run_cancel", run_id=run_id)) == f"Run {run_id} cancelled."
    assert "failed (cancelled)" in _said(await tool(http, auth, "project_run_get", run_id=run_id))
    assert _said(await tool(http, auth, "project_delete", slug="site-crew")) == "Deleted site-crew and its runs."


async def test_a_projects_tools_answer_to_a_swarms_names_and_say_the_runs_pull_request(
    on_rrotor: OnRrotor, engine: AsyncEngine
) -> None:
    ada, rt, bots = await crew_on_rrotor(on_rrotor, engine)
    _, auth = await granted(engine, ada, RESOURCE)
    http = on_rrotor.s.http
    made = {"name": "Site crew", "repo_url": REPO, "members": [b["id"] for b in bots], "review": "end", "max_turns": 1}
    made["runs_on"] = str(rt.id)
    said = _said((await rpc(http, auth, "tools/call", name="swarm_create", arguments=made))["result"])
    assert "Made Site crew" in said
    assert "site-crew" in _said(await tool(http, auth, "swarms")) and "Site crew" in _said(
        await tool(http, auth, "swarm", slug="site-crew")
    )
    listed = (await rpc(http, auth, "tools/list"))["result"]["tools"]
    names = {t["name"] for t in listed}
    assert "project_run" in names and not {n for n in names if n.startswith("swarm")}
    started = await tool(http, auth, "swarm_run", slug="site-crew", task="Go")
    run_id = started["structuredContent"]["id"]
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, turned())
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, {"status": "done", "data": {"status": "merged"}})
    said = _said(await tool(http, auth, "swarm_run_get", run_id=run_id))
    assert f"needs_input (max_turns). Its pull request: {REPO}/pull/1." in said
    assert "Merge PR #1, the whole run?" in _said(await tool(http, auth, "bot_approvals"))


async def test_a_bots_run_on_its_rrotor_says_where_it_is(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada = await person(engine)
    rt = await online(engine, ada)
    await made_bot(on_rrotor.s, ada, runs_on=str(rt.id))
    _, auth = await granted(engine, ada, RESOURCE)
    started = await tool(on_rrotor.s.http, auth, "bot_run", slug="inbox-cat", input="lunch")
    assert "dispatched" in _said(started)
    run_id = uuid.UUID(started["structuredContent"]["id"])
    await on_rrotor.landed(rt, ada, run_id, result("needs_input", question="Send it?", options=["yes", "no"]))
    assert f"on rrotor {rt.id}: needs_input" in _said(await tool(on_rrotor.s.http, auth, "bot_approvals"))
