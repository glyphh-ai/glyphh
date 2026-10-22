"""A model's life through the Ada API at its own host: made from a spec, loaded, asked, graded, forgotten, learned,
calibrated and deleted, each answered by a worker."""

import asyncio
from multiprocessing.process import BaseProcess
from typing import Any

import httpx
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.process import Worker
from tests.ada.conftest import SHAPES, a_model, an_org, cases, rid, shape, start_process


async def _job(ada: httpx.AsyncClient, key: dict[str, str], job: dict[str, Any]) -> dict[str, Any]:
    for _ in range(200):
        got = (await ada.get(f"/v1/jobs/{job['id']}", headers=key)).json()
        if got["state"] in ("done", "failed"):
            return dict(got)
        await asyncio.sleep(0.1)
    raise AssertionError(f"job {job['id']} never finished")


async def test_a_model_is_made_loaded_and_asked(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    _, key = await an_org(engine, ada)
    made = await a_model(ada, key)
    assert (made["name"], made["version"], made["precedents"]) == ("shapes", 1, 0)
    many = (await ada.post("/v1/models/shapes/record_many", json={"cases": cases(40)}, headers=key)).json()
    assert (many["added"], many["replaced"], many["precedents"]) == (40, 0, 40)
    again = await ada.post("/v1/models/shapes/record_many", json={"cases": cases(5)}, headers=key)
    assert (again.json()["added"], again.json()["replaced"]) == (0, 5)  # the key part replaces its row
    one = (await ada.post("/v1/models/shapes/record", json={"data": shape(99), "outcome": "good"}, headers=key)).json()
    assert one == {"id": rid(99), "precedents": 41}
    ask = {"data": shape(1000, "r", 3)}
    query = (await ada.post("/v1/models/shapes/query", json=ask, headers=key)).json()
    assert query["sufficient"] and query["top"] == "good" and query["receipts"]
    probs = (await ada.post("/v1/models/shapes/probabilities", json=ask, headers=key)).json()
    assert set(probs) == {"good", "bad"} and abs(sum(probs.values()) - 1) < 0.01
    facts = (await ada.post("/v1/models/shapes/facts", json={**ask, "top": 2}, headers=key)).json()
    assert len(facts) == 2 and "tree" in facts[0]
    decided = (await ada.post("/v1/models/shapes/decide", json={**ask, "include": ["facts"]}, headers=key)).json()
    assert decided["outcome"] == "good" and decided["receipts"] and len(decided["facts"]) == 1
    headline = (await ada.post("/v1/decide", json={"model": "shapes", **ask}, headers=key)).json()
    assert (headline["model"], headline["version"], headline["outcome"]) == ("shapes", 1, "good")
    assert set(headline) >= {"outcome", "probabilities", "expected_cost", "ask", "receipts"}


async def test_cases_are_graded_and_forgotten(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=12)
    graded = await ada.post("/v1/models/shapes/grade", json={"id": rid(1), "value": "bad"}, headers=key)
    assert graded.json() == {"id": rid(1), "output": "default", "value": "bad"}
    gone = await ada.delete(f"/v1/models/shapes/precedents/{rid(1)}", headers=key)
    assert gone.json() == {"id": rid(1), "forgotten": True, "precedents": 11}
    missing = await ada.delete(f"/v1/models/shapes/precedents/{rid(1)}", headers=key)
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "E_PRECEDENT_MISSING")
    wrong = await ada.post("/v1/models/shapes/grade", json={"id": rid(2), "output": "no", "value": "x"}, headers=key)
    assert (wrong.status_code, wrong.json()["error"]["code"]) == (422, "E_SPEC")
    empty = await ada.post("/v1/models/shapes/grade", json={"id": rid(2), "value": ""}, headers=key)
    assert (empty.status_code, empty.json()["error"]["code"]) == (422, "E_INVALID")


async def test_models_are_listed_read_and_deleted(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    _, key = await an_org(engine, ada)
    assert (await ada.get("/v1/models", headers=key)).json() == {"models": []}
    nothing = await ada.get("/v1/models/shapes", headers=key)
    assert (nothing.status_code, nothing.json()["error"]["code"]) == (404, "E_MODEL_MISSING")
    await a_model(ada, key, n=3)
    await a_model(ada, key, "second")
    listed = (await ada.get("/v1/models", headers=key)).json()["models"]
    assert [(m["name"], m["precedents"]) for m in listed] == [("second", 0), ("shapes", 3)]
    read = (await ada.get("/v1/models/shapes", headers=key)).json()
    assert read["spec"]["name"] == "shapes" and read["precedents"] == 3
    twice = await ada.post("/v1/models", json={"name": "shapes", "spec": {"name": "x"}}, headers=key)
    assert twice.status_code == 422 and twice.json()["error"]["code"] == "E_SPEC"
    unconfirmed = await ada.delete("/v1/models/shapes?confirm=other", headers=key)
    assert unconfirmed.status_code == 409
    assert (await ada.delete("/v1/models/shapes?confirm=shapes", headers=key)).json() == {
        "name": "shapes",
        "deleted": True,
    }
    assert (await ada.get("/v1/models/shapes", headers=key)).status_code == 404
    assert (await ada.delete("/v1/models/shapes?confirm=shapes", headers=key)).status_code == 404
    again = await a_model(ada, key, n=2)  # the name is free again, the model new and empty but for its cases
    assert again["precedents"] == 0


async def test_an_orgs_first_models_made_at_once_by_many_workers(
    engine: AsyncEngine, ada: httpx.AsyncClient, streams: Redis, spawn: list[BaseProcess]
) -> None:
    """Worker processes making one org's first models at once: one makes its schema, the others, waiting on its
    lock, see it made (they once failed: a backend's catalog does not move while it waits on an advisory lock)."""
    _, before = await an_org(engine, ada)
    _, key = await an_org(engine, ada)
    for _ in range(4):
        start_process(spawn)
    for _ in range(1000):  # every process has joined the group
        if streams.exists("ada:sync") and len(streams.xinfo_consumers("ada:sync", "ada")) >= 4:
            break
        await asyncio.sleep(0.01)
    await a_model(ada, before)  # the processes have served another org first, as long-running ones have
    assert {r.status_code for r in await asyncio.gather(*(ada.get("/v1/models", headers=before) for _ in range(16)))}
    new = (ada.post("/v1/models", json={"name": f"m{n}", "spec": SHAPES}, headers=key) for n in range(9))
    made = await asyncio.gather(*new)
    assert [m.status_code for m in made] == [201] * 9, [m.text for m in made if m.status_code != 201]
    loads = (ada.post(f"/v1/models/m{n}/record_many", json={"cases": cases(5)}, headers=key) for n in range(9))
    assert {r.status_code for r in await asyncio.gather(*loads)} == {200}
    gone = (ada.delete(f"/v1/models/m{n}?confirm=m{n}", headers=key) for n in range(9))
    assert {r.status_code for r in await asyncio.gather(*gone)} == {200}


async def test_learn_and_calibrate_are_jobs(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=60)
    started = await ada.post("/v1/models/shapes/learn", headers=key)
    assert started.status_code == 202 and started.json()["state"] == "queued"
    learned = await _job(ada, key, started.json())
    assert learned["state"] == "done" and learned["percent"] == 100
    assert learned["result"]["precedents"] == 60 and learned["result"]["learned"]["roles"]
    assert learned["result"]["tau"] > 0
    calibrated = await _job(ada, key, (await ada.post("/v1/models/shapes/calibrate", headers=key)).json())
    assert calibrated["state"] == "done" and "learned" not in calibrated["result"]
    after = (await ada.post("/v1/decide", json={"model": "shapes", "data": shape(7, "g", 9)}, headers=key)).json()
    assert after["outcome"] == "good"


async def test_a_job_that_cannot_learn_fails_with_why(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=3)
    failed = await _job(ada, key, (await ada.post("/v1/models/shapes/learn", headers=key)).json())
    assert failed["state"] == "failed" and failed["error"]["code"] == "E_SPEC"
    missing = await ada.get("/v1/jobs/not-a-job", headers=key)
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "E_JOB_MISSING")
