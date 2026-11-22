"""The connector's swarm tools: a swarm made, read, changed, run, its pull request merged from the chat (and shown in
bot_approvals beside the bots' questions), its run cancelled, the swarm deleted; and a bot's run on its rrotor as
the bot tools tell it."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from tests.bots.conftest import made_bot
from tests.bots.remote import REMOTE, OnRrotor, online, result, rrotor_fixture  # noqa: F401 (the fixture)
from tests.connector import granted, rpc, tool
from tests.db.helpers import person
from tests.swarms.test_swarms import REPO, _crew, _turned

RESOURCE: str = REMOTE.mcp_resource


def _said(got: dict[str, Any]) -> str:
    assert not got.get("isError"), got
    return str(got["content"][0]["text"])


async def test_a_swarm_is_made_run_and_merged_from_the_chat(on_rrotor: OnRrotor, engine: AsyncEngine) -> None:
    ada, rt, crew = await _crew(on_rrotor, engine)
    _, auth = await granted(engine, ada, RESOURCE)
    http = on_rrotor.s.http
    assert _said(await tool(http, auth, "swarms")) == "The org has no swarms yet."
    made = {"name": "Site crew", "repo_url": REPO, "members": [b["id"] for b in crew], "runs_on": str(rt.id)}
    assert "Made Site crew (site-crew): https://github.com/acme/site on main, crew Ada Cat, Bo Cat" in _said(
        (await rpc(http, auth, "tools/call", name="swarm_create", arguments=made))["result"]
    )
    assert "1 rounds, review each_turn" in _said(await tool(http, auth, "swarm", slug="site-crew"))
    assert "review auto" in _said(await tool(http, auth, "swarm_update", slug="site-crew", review="auto"))
    await tool(http, auth, "swarm_update", slug="site-crew", review="each_turn")
    assert "site-crew" in _said(await tool(http, auth, "swarms"))
    assert _said(await tool(http, auth, "swarm_runs", slug="site-crew")) == "No runs yet."
    started = await tool(http, auth, "swarm_run", slug="site-crew", task="Make the home page")
    assert "of site-crew: running. turn 1 Ada Cat: running" in _said(started)
    run_id = started["structuredContent"]["id"]
    await on_rrotor.landed(rt, ada, on_rrotor.hub.last().run_id, _turned())
    queue = _said(await tool(http, auth, "bot_approvals"))
    assert f"Swarm run {run_id} of site-crew: It asks: Merge PR #7 by Ada Cat? (merge, reject)" in queue
    assert f"turn 1 Ada Cat: open {REPO}/pull/7" in _said(await tool(http, auth, "swarm_run_get", run_id=run_id))
    assert "merging" in _said(await tool(http, auth, "swarm_run_answer", run_id=run_id, answer="merge"))
    assert run_id in _said(await tool(http, auth, "swarm_runs", slug="site-crew"))
    assert _said(await tool(http, auth, "swarm_run_cancel", run_id=run_id)) == f"Run {run_id} cancelled."
    assert "failed (cancelled)" in _said(await tool(http, auth, "swarm_run_get", run_id=run_id))
    assert _said(await tool(http, auth, "swarm_delete", slug="site-crew")) == "Deleted site-crew and its runs."


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
