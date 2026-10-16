"""Runs over the API: a call of the person's model goes down their runtime's link with the caller's clearance and
is `running` until the link answers; a run is read, listed and paged, answered only while waiting, cancelled only
before it ends; each person sees only their own; a runtime no process holds keeps nothing."""

import uuid

import httpx
from redis.asyncio import Redis
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import Run
from tests.api.test_models import _error
from tests.db.helpers import Person, person
from tests.link import Rt, a_model, deploy, holding, local_runtime


async def _set(engine: AsyncEngine, run_id: str, status: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(update(Run).where(Run.id == uuid.UUID(run_id)).values(status=status))


async def _ready(engine: AsyncEngine, who: Person, name: str = "leads") -> Rt:
    """A deployed model on the person's local runtime: the runtime."""
    rt = await local_runtime(engine, who)
    _, v1, _ = await a_model(engine, who, name=name)
    await deploy(engine, rt.id, v1)
    return rt


async def test_a_call_goes_down_the_link_with_its_clearance_and_the_run_is_read_until_it_ends(
    client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    ada = await person(engine, "Pro")
    rt = await _ready(engine, ada)
    body = {"model": "leads", "function": "fetch", "inputs": {"since": "monday"}, "clearance": 0.4}
    async with holding(redis, rt.id) as sent:
        res = await client.post("/v1/runs", json=body, headers=ada.headers)
        assert res.status_code == 201, res.text
        run = res.json()
        call = await sent()
        assert (call["type"], call["run_id"], call["function"], call["inputs"], call["caller"], call["clearance"]) == (
            "call",
            run["id"],
            "fetch",
            {"since": "monday"},
            "claude",
            0.4,
        )
        assert (run["model"], run["version"], run["status"], run["runtime_id"], run["ended_at"]) == (
            "leads",
            1,
            "running",
            str(rt.id),
            None,
        )
        routine = {"model": "leads", "caller": "routine", "version": 2}
        res = await client.post("/v1/runs", json=routine, headers=ada.headers)
        assert (res.status_code, res.json()["version"], res.json()["function"], res.json()["caller"]) == (
            201,
            2,
            "start",
            "routine",
        )
        assert (await sent())["clearance"] == 1.0
        waiting = _error(
            await client.post(f"/v1/runs/{run['id']}/continue", json={}, headers=ada.headers), 409, "E_CONFLICT"
        )
        assert waiting["status"] == "running"
        await _set(engine, run["id"], "needs_input")
        res = await client.post(f"/v1/runs/{run['id']}/continue", json={"answer": "yes"}, headers=ada.headers)
        assert res.status_code == 200 and res.json()["status"] == "running"
        cont = await sent()
        assert (cont["type"], cont["run_id"], cont["answer"]) == ("continue", run["id"], "yes")
        res = await client.post(f"/v1/runs/{run['id']}/cancel", headers=ada.headers)
        assert res.status_code == 200 and res.json()["status"] == "running"
        assert (await sent())["type"] == "cancel"
    await _set(engine, run["id"], "done")
    got = (await client.get(f"/v1/runs/{run['id']}", headers=ada.headers)).json()
    assert got["status"] == "done"
    ended = _error(await client.post(f"/v1/runs/{run['id']}/cancel", headers=ada.headers), 409, "E_CONFLICT")
    assert ended["status"] == "done"


async def test_runs_are_listed_newest_first_filtered_and_paged_each_persons_own(
    client: httpx.AsyncClient, engine: AsyncEngine, redis: Redis
) -> None:
    ada = await person(engine, "Pro")
    rt = await _ready(engine, ada)
    ids = []
    async with holding(redis, rt.id) as sent:
        for function in ("a", "b", "c"):
            res = await client.post("/v1/runs", json={"model": "leads", "function": function}, headers=ada.headers)
            ids.append(res.json()["id"])
            await sent()
    await _set(engine, ids[0], "done")
    listed = (await client.get("/v1/runs", headers=ada.headers)).json()
    assert [r["function"] for r in listed] == ["c", "b", "a"]
    done = (await client.get("/v1/runs", params={"status": "done"}, headers=ada.headers)).json()
    assert [r["id"] for r in done] == [ids[0]]
    assert (await client.get("/v1/runs", params={"model": "other"}, headers=ada.headers)).json() == []
    page = (await client.get("/v1/runs", params={"limit": 2}, headers=ada.headers)).json()
    rest = (await client.get("/v1/runs", params={"before": page[-1]["started_at"]}, headers=ada.headers)).json()
    assert [r["function"] for r in page] + [r["function"] for r in rest] == ["c", "b", "a"]
    eve = await person(engine)
    assert (await client.get("/v1/runs", headers=eve.headers)).json() == []
    for method, path in (
        ("GET", f"/v1/runs/{ids[0]}"),
        ("POST", f"/v1/runs/{ids[0]}/continue"),
        ("POST", f"/v1/runs/{ids[0]}/cancel"),
    ):
        body = {} if "continue" in path else None
        _error(await client.request(method, path, json=body, headers=eve.headers), 404, "E_NOT_FOUND")


async def test_a_call_needs_a_model_a_runtime_and_its_link_or_keeps_nothing(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Pro")
    none = _error(await client.post("/v1/runs", json={"model": "leads"}, headers=ada.headers), 404, "E_NOT_FOUND")
    assert none["model"] == "leads"
    await a_model(engine, ada, name="leads")
    assert (
        _error(await client.post("/v1/runs", json={"model": "leads"}, headers=ada.headers), 404, "E_NOT_FOUND")[
            "reason"
        ]
        == "no_runtime"
    )
    rt = await local_runtime(engine, ada)
    _error(
        await client.post("/v1/runs", json={"model": "leads"}, headers=ada.headers), 404, "E_NOT_FOUND"
    )  # no version active
    off = _error(
        await client.post("/v1/runs", json={"model": "leads", "version": 1}, headers=ada.headers), 503, "E_UNAVAILABLE"
    )
    assert (off["reason"], off["runtime_id"]) == ("runtime_offline", str(rt.id))
    assert (await client.get("/v1/runs", headers=ada.headers)).json() == []
    bad = await client.post("/v1/runs", json={"model": "leads", "clearance": 2}, headers=ada.headers)
    assert bad.status_code == 422
