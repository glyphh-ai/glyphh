"""The connector's model tools: the person's models, a call as the person (clearance 1), a run read and answered,
and refusals as tool errors."""

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api.test_mcp_tools import _refused
from tests.api.test_models import with_ada
from tests.api.test_runs import _set
from tests.connector import granted, rpc, tool
from tests.link import SHA, deploy, holding, local_runtime


async def test_models_are_listed_called_and_their_runs_read_and_answered(
    client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    ada = await with_ada(engine)
    _, auth = await granted(engine, ada)
    empty = await tool(client, auth, "models_list")
    assert (empty["content"][0]["text"], empty["structuredContent"]) == ("You have no models.", {"models": []})
    model = (await client.post("/v1/models", json={"name": "leads", "repo": "octo/leads"}, headers=ada.headers)).json()
    v1 = await client.post(
        f"/v1/models/{model['id']}/versions", json={"commit_sha": SHA, "manifest": {}}, headers=ada.headers
    )
    listed = await tool(client, auth, "models_list")
    assert listed["content"][0]["text"] == "leads: 1 versions, not deployed, octo/leads"
    rt = await local_runtime(engine, ada)
    await deploy(engine, rt.id, v1.json()["id"])
    listed = await tool(client, auth, "models_list")
    assert listed["content"][0]["text"] == "leads: 1 versions, active v1, octo/leads"
    assert listed["structuredContent"]["models"][0]["versions"][0]["active_on"] == [str(rt.id)]
    async with holding(redis, rt.id) as sent:
        called = await tool(client, auth, "call", model="leads", inputs={"since": "monday"})
        run = called["structuredContent"]
        message = await sent()
        assert (message["caller"], message["clearance"], message["inputs"]) == ("claude", 1.0, {"since": "monday"})
        assert (
            called["content"][0]["text"]
            == f"leads v1 start: running (run {run['id']}); call run_status for its result."
        )
        _refused(await tool(client, auth, "continue", run_id=run["id"], answer="yes"), "E_CONFLICT")
        await _set(engine, run["id"], "needs_input")
        resumed = await tool(client, auth, "continue", run_id=run["id"], answer="yes")
        assert resumed["content"][0]["text"] == f"leads v1 start: running (run {run['id']})"
        assert (await sent())["answer"] == "yes"
    await _set(engine, run["id"], "done")
    status = await tool(client, auth, "run_status", run_id=run["id"])
    assert status["content"][0]["text"] == f"leads v1 start: done (run {run['id']})"
    assert status["structuredContent"]["status"] == "done"
    _refused(await tool(client, auth, "call", model="nothing"), "E_NOT_FOUND")
    _refused(await tool(client, auth, "call"), "E_INVALID")
    names = {t["name"] for t in (await rpc(client, auth, "tools/list"))["result"]["tools"]}
    assert names >= {"models_list", "call", "continue", "run_status"}
