"""Tuning: every change of a spec or its settings is a new version; a read lever goes live at once on the same store,
a change of what a case carries re-encodes into a store of its own while the old one serves, writes made meanwhile
included; any version can be made active again, at once or by a job that brings its store up to date."""

from typing import Any

import httpx
import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import catalog, jobs, pg
from glyphh_ada.handlers import handle
from glyphh_ada.process import Worker
from glyphh_ada.protocol import JOBS, Message
from tests.ada.conftest import ADA, SHAPES, a_model, an_org, cases, finished, rid, shape
from tests.conftest import DATABASE_URL


def _sql(org: str, text: str, params: tuple = ()) -> list[tuple]:
    with psycopg.connect(pg.libpq_url(DATABASE_URL), autocommit=True) as conn:
        pg.enter(conn, org)
        found = conn.execute(text.replace("{s}", f'"{pg.schema_for(org)}"'), params)
        return found.fetchall() if found.description else []


async def _version(ada: httpx.AsyncClient, key: dict[str, str]) -> int:
    return int((await ada.get("/v1/models/shapes", headers=key)).json()["version"])


async def test_a_read_lever_is_a_new_version_live_at_once(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=60)
    await finished(ada, key, (await ada.post("/v1/models/shapes/learn", headers=key)).json())
    levers = (await ada.get("/v1/models/shapes/settings", headers=key)).json()
    assert levers["version"] == 1 and levers["settings"]["k"] == 15 and "word_evidence" in levers["settings"]
    changed = await ada.patch("/v1/models/shapes/settings", json={"changes": {"k": 5}, "note": "fewer"}, headers=key)
    assert changed.json() == {"version": 2, "active": True, "job": None}, changed.text
    assert (await ada.get("/v1/models/shapes/settings", headers=key)).json()["settings"]["k"] == 5
    decided = (await ada.post("/v1/decide", json={"model": "shapes", "data": shape(3)}, headers=key)).json()
    assert decided["version"] == 2 and len(decided["receipts"]) <= 5
    same = await ada.patch("/v1/models/shapes/settings", json={"changes": {"k": 5}}, headers=key)
    assert (same.status_code, same.json()["error"]["code"]) == (409, "E_NO_CHANGE")
    wrong = await ada.patch("/v1/models/shapes/settings", json={"changes": {"k": "many"}}, headers=key)
    assert (wrong.status_code, wrong.json()["error"]["code"]) == (422, "E_SPEC")
    recal = await ada.patch("/v1/models/shapes/settings", json={"changes": {"calibrate_sample": 50}}, headers=key)
    assert recal.json()["active"] and recal.json()["job"]["kind"] == "calibrate"
    assert (await finished(ada, key, recal.json()["job"]))["state"] == "done"
    back = await ada.post("/v1/models/shapes/versions/1/activate", headers=key)
    assert back.json() == {"version": 1, "active": True, "job": None}
    assert (await ada.post("/v1/models/shapes/versions/1/activate", headers=key)).json()["active"]
    listed = (await ada.get("/v1/models/shapes/versions", headers=key)).json()["versions"]
    assert [(v["version"], v["active"], v["note"], v["reencoded"]) for v in listed] == [
        (1, True, "made", False),
        (2, False, "fewer", False),
        (3, False, "", False),
    ]
    assert (await ada.post("/v1/models/shapes/versions/9/activate", headers=key)).status_code == 404


def _writes_meanwhile(org: str) -> Any:
    """A stand-in for learning in a re-encode: writes come in through a sync worker while it runs."""
    real = jobs.fit
    other = Worker(ADA, JOBS)

    def fit(*args: Any, **kw: Any) -> Any:
        handle(other.ctx, Message(org, "shapes", "record_many", {"cases": cases(5, start=100)}))
        handle(other.ctx, Message(org, "shapes", "forget", {"id": rid(0)}))
        handle(other.ctx, Message(org, "shapes", "grade", {"id": rid(1), "value": "bad"}))
        return real(*args, **kw)

    return fit, other


async def test_a_reencode_writes_a_new_store_and_keeps_the_writes_made_meanwhile(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    who, key = await an_org(engine, ada)
    org = str(who.org_id)
    await a_model(ada, key, n=60)
    fit, other = _writes_meanwhile(org)
    monkeypatch.setattr(jobs, "fit", fit)
    moved = await ada.put("/v1/models/shapes/spec", json={"spec": {**SHAPES, "seed": 11}, "note": "seed"}, headers=key)
    assert moved.json()["active"] is False and moved.json()["job"]["kind"] == "reencode", moved.text
    done = await finished(ada, key, moved.json()["job"])
    other.ctx.conn.close()
    assert done["state"] == "done" and done["result"]["precedents"] == 64, done
    assert await _version(ada, key) == 2
    assert (await ada.get("/v1/models/shapes", headers=key)).json()["precedents"] == 64
    graded = _sql(org, "SELECT outcome FROM {s}.precedents WHERE id = %s AND model LIKE '%%v2'", (rid(1),))
    assert graded == [("bad",)]
    assert _sql(org, "SELECT count(*) FROM {s}.precedents WHERE id = %s AND model LIKE '%%v2'", (rid(0),)) == [(0,)]
    after = await ada.post("/v1/models/shapes/record", json={"data": shape(200), "outcome": "good"}, headers=key)
    assert after.status_code == 200
    back = (await ada.post("/v1/models/shapes/versions/1/activate", headers=key)).json()
    assert back["active"] is False and back["job"]["args"] == {"version": 1, "sync": True}
    synced = await finished(ada, key, back["job"])
    assert synced["state"] == "done" and synced["result"]["store"] == "synced"
    assert await _version(ada, key) == 1
    assert (await ada.get("/v1/models/shapes", headers=key)).json()["precedents"] == 65  # the write made on v2 too
    listed = (await ada.get("/v1/models/shapes/versions", headers=key)).json()["versions"]
    assert [(v["version"], v["reencoded"]) for v in listed] == [(1, False), (2, True)]


async def test_what_a_version_change_refuses(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    org = str(who.org_id)
    await a_model(ada, key, n=12)
    reading = {**SHAPES, "layers": [dict(SHAPES["layers"][0], segments=[dict(SHAPES["layers"][0]["segments"][0])])]}
    reading["layers"][0]["segments"][0]["roles"] = [
        {**r, "numeric_config": {"min_value": 0, "max_value": 20, "bin_width": 2}} if r["name"] == "size" else r
        for r in SHAPES["layers"][0]["segments"][0]["roles"]
    ]
    refused = await ada.put("/v1/models/shapes/spec", json={"spec": reading}, headers=key)
    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "E_SPEC_READING")
    assert refused.json()["error"]["roles"] == ["a.s.size"]
    moved = (await ada.put("/v1/models/shapes/spec", json={"spec": {**SHAPES, "seed": 12}}, headers=key)).json()
    await finished(ada, key, moved["job"])
    _sql(org, "UPDATE {s}.spec_versions SET retired_at = now() - interval '8 days' WHERE version = 1")
    again = (await ada.put("/v1/models/shapes/spec", json={"spec": {**SHAPES, "seed": 13}}, headers=key)).json()
    assert (await finished(ada, key, again["job"]))["state"] == "done"
    gone = await ada.post("/v1/models/shapes/versions/1/activate", headers=key)
    assert (gone.status_code, gone.json()["error"]["code"]) == (410, "E_VERSION_GONE")
    listed = (await ada.get("/v1/models/shapes/versions", headers=key)).json()["versions"]
    assert [v["gone"] for v in listed] == [True, False, False]


async def test_a_version_still_being_made_waits(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    who, key = await an_org(engine, ada)
    org = str(who.org_id)
    await a_model(ada, key, n=5)
    moved = (await ada.put("/v1/models/shapes/spec", json={"spec": {**SHAPES, "seed": 14}}, headers=key)).json()
    assert moved["job"]["state"] == "queued"
    waiting = await ada.post("/v1/models/shapes/versions/2/activate", headers=key)
    assert (waiting.status_code, waiting.json()["error"]["code"]) == (409, "E_NOT_READY")
    busy = await ada.patch("/v1/models/shapes/settings", json={"changes": {"lexicon": False}}, headers=key)
    assert (busy.status_code, busy.json()["error"]["code"]) == (409, "E_BUSY")
    jobs_side = Worker(ADA, JOBS)
    schema = pg.enter(jobs_side.ctx.conn, org)
    work = Message(org, "shapes", "reencode", {"job": moved["job"]["id"]})
    jobs_side.dispatch(work)
    made = jobs.view(jobs_side.ctx.conn, schema, moved["job"]["id"])
    assert made["state"] == "done" and made["result"]["learned"]["error"]["code"] == "E_SPEC"  # five cases: none
    found = catalog.live(jobs_side.ctx.conn, schema, "shapes")
    again = jobs.add(jobs_side.ctx.conn, schema, found.id, "reencode", {"version": 2}, "t")
    jobs_side.dispatch(Message(org, "shapes", "reencode", {"job": again}))
    assert jobs.view(jobs_side.ctx.conn, schema, again)["result"] == {"version": 2, "active": True, "copied": 0}
    _sql(org, "UPDATE {s}.spec_versions SET gone = true WHERE version = 1")
    lost = jobs.add(jobs_side.ctx.conn, schema, found.id, "reencode", {"version": 1, "sync": True}, "t")
    jobs_side.dispatch(Message(org, "shapes", "reencode", {"job": lost}))
    assert jobs.view(jobs_side.ctx.conn, schema, lost)["error"]["code"] == "E_VERSION_GONE"
    jobs_side.ctx.conn.close()


async def test_a_reencode_that_never_finished_is_dropped_by_the_next(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    org = str(who.org_id)
    await a_model(ada, key, n=12)
    failed = (await ada.put("/v1/models/shapes/spec", json={"spec": {**SHAPES, "seed": 21}}, headers=key)).json()
    _sql(org, "UPDATE {s}.jobs SET state = 'failed' WHERE id = %s", (failed["job"]["id"],))
    after = (await ada.put("/v1/models/shapes/spec", json={"spec": {**SHAPES, "seed": 22}}, headers=key)).json()
    assert after["version"] == 3
    jobs_side = Worker(ADA, JOBS)
    jobs_side.dispatch(Message(org, "shapes", "reencode", {"job": after["job"]["id"]}))
    jobs_side.ctx.conn.close()
    listed = (await ada.get("/v1/models/shapes/versions", headers=key)).json()["versions"]
    assert [(v["version"], v["active"], v["gone"]) for v in listed] == [
        (1, False, False),
        (2, False, True),
        (3, True, False),
    ]


async def test_refresh_every_starts_a_learn_job(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key, n=15)
    await ada.patch("/v1/models/shapes/settings", json={"changes": {"refresh_every": 20}}, headers=key)
    await ada.post("/v1/models/shapes/record_many", json={"cases": cases(4, start=15)}, headers=key)
    learns = "SELECT count(*) FROM {s}.jobs WHERE kind = 'learn'"
    assert _sql(str(who.org_id), learns) == [(0,)]
    await ada.post("/v1/models/shapes/record", json={"data": shape(19), "outcome": "good"}, headers=key)
    assert _sql(str(who.org_id), learns) == [(1,)]
