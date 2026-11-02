"""A job never sits forever and can always be stopped (2026-11-02): its stage says what it is doing, a running job whose
worker is gone is failed E_JOB_STALLED, one that stopped its worker MAX_DELIVERIES times E_JOB_LOST, and cancel ends
one not started at once and a running one at its next step, saying what of its work stays."""

import threading
from typing import Any

import httpx
import psycopg
import pytest
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import jobstate, pg, process, protocol, runner
from glyphh_ada.jobstate import Beat
from glyphh_ada.process import Worker
from glyphh_ada.protocol import GROUP, JOBS, SYNC, Message
from tests.ada.conftest import ADA, SHAPES, a_model, an_org, finished
from tests.ada.mcp import data, refused, signed_in, text, tool
from tests.db.helpers import person


@pytest.fixture
def idle(worker: Worker) -> Any:
    """A jobs worker that is not serving: its parts called by the test, on its own connection (a sync worker serves
    the API's requests beside it)."""
    made = Worker(ADA, JOBS)
    yield made
    made.ctx.conn.close()


async def _queued(engine: AsyncEngine, ada: httpx.AsyncClient, kind: str = "learn") -> tuple[Any, dict, dict]:
    """An org with a model of 20 cases, and a job of this kind queued on it (no jobs worker runs it)."""
    who, key = await an_org(engine, ada)
    await a_model(ada, key, n=20)
    path = {"learn": "learn", "export": "export"}[kind]
    job = (await ada.post(f"/v1/models/shapes/{path}", headers=key)).json()
    assert job["state"] == "queued" and job["stage"] is None
    return who, key, job


def _sql(idle: Worker, org: str, text_: str, *args: Any) -> None:
    schema = pg.enter(idle.ctx.conn, org)
    idle.ctx.conn.execute(text_.replace("{s}", f'"{schema}"'), args)


def _work(idle: Worker, org: str, job: dict) -> None:
    process.work(idle.ctx, Message(org, "shapes", job["kind"], {"job": job["id"]}), idle)


async def test_a_queued_job_is_cancelled_at_once_and_an_ended_one_is_refused(
    engine: AsyncEngine, ada: httpx.AsyncClient, idle: Worker
) -> None:
    who, key, job = await _queued(engine, ada)
    cancelled = (await ada.post(f"/v1/jobs/{job['id']}/cancel", headers=key)).json()
    assert cancelled["state"] == "failed" and cancelled["error"]["code"] == "E_CANCELLED"
    assert cancelled["error"]["message"].endswith("It had not started: nothing of it was done.")
    again = await ada.post(f"/v1/jobs/{job['id']}/cancel", headers=key)
    assert again.status_code == 200 and again.json() == cancelled
    _work(idle, str(who.org_id), job)  # its message taken later: nothing runs
    assert (await ada.get(f"/v1/jobs/{job['id']}", headers=key)).json() == cancelled
    done = (await ada.post("/v1/models/shapes/calibrate", headers=key)).json()
    _work(idle, str(who.org_id), done)
    ended = await ada.post(f"/v1/jobs/{done['id']}/cancel", headers=key)
    assert (ended.status_code, ended.json()["error"]["code"]) == (409, "E_JOB_ENDED")
    missing = await ada.post("/v1/jobs/not-a-job/cancel", headers=key)
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "E_JOB_MISSING")


async def test_a_running_job_stops_at_its_next_step(engine: AsyncEngine, ada: httpx.AsyncClient, idle: Worker) -> None:
    who, key, job = await _queued(engine, ada)
    org = str(who.org_id)
    _sql(idle, org, "UPDATE {s}.jobs SET state = 'running', started_at = now() WHERE id = %s", job["id"])
    asked = (await ada.post(f"/v1/jobs/{job['id']}/cancel", headers=key)).json()
    assert (asked["state"], asked["stage"]) == ("running", "cancelling")
    _work(idle, org, job)  # taken again (its worker died): it stops at its first step, before learning anything
    stopped = (await ada.get(f"/v1/jobs/{job['id']}", headers=key)).json()
    assert stopped["state"] == "failed" and stopped["stage"] is None
    assert stopped["error"]["message"] == f"Cancelled by {asked['made_by']}. The model is as it was before this learn."


async def test_a_learn_cancelled_once_it_has_learned_says_so(
    engine: AsyncEngine, ada: httpx.AsyncClient, idle: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    who, key, job = await _queued(engine, ada)
    org = str(who.org_id)

    def run(conn: psycopg.Connection, schema: str, job: dict, progress: Any, *_: Any) -> dict:
        progress(jobstate.LEARNED_AT, "restating 0 of 20 precedents")
        conn.execute(f'UPDATE "{schema}".jobs SET cancel_by = %s WHERE id = %s', ("someone", job["id"]))
        progress(75.0, "restating 10 of 20 precedents")
        raise AssertionError("not reached")

    monkeypatch.setattr(runner, "run", run)
    _work(idle, org, job)
    stopped = (await ada.get(f"/v1/jobs/{job['id']}", headers=key)).json()
    assert stopped["error"]["message"] == f"Cancelled by someone. {jobstate.LEARNED_KEPT}"
    assert stopped["percent"] == 75.0


async def test_a_running_job_whose_worker_is_gone_is_failed_when_looked_at(
    engine: AsyncEngine, ada: httpx.AsyncClient, idle: Worker, streams: Redis
) -> None:
    who, key, job = await _queued(engine, ada)
    org = str(who.org_id)
    long_ago = (
        "UPDATE {s}.jobs SET state = 'running', percent = %s, started_at = now() - interval '1 hour' WHERE id = %s"
    )
    _sql(idle, org, long_ago, 84.5, job["id"])
    jobstate.beat(streams, job["id"])  # its worker still beats: running, however long
    assert (await ada.get(f"/v1/jobs/{job['id']}", headers=key)).json()["state"] == "running"
    streams.delete(protocol.job_beat_key(job["id"]))  # the worker died, and no other took the job up
    stalled = (await ada.get(f"/v1/jobs/{job['id']}", headers=key)).json()
    assert (stalled["state"], stalled["percent"], stalled["error"]) == ("failed", 84.5, jobstate.STALLED)
    # One someone had asked to cancel ends cancelled, by where it was: a learn past its weights says so.
    for percent, kept in ((20.0, jobstate.KEPT["learn"]), (70.0, jobstate.LEARNED_KEPT)):
        other = (await ada.post("/v1/models/shapes/learn", headers=key)).json()
        _sql(idle, org, long_ago, percent, other["id"])
        _sql(idle, org, "UPDATE {s}.jobs SET cancel_by = 'ann' WHERE id = %s", other["id"])
        ended = (await ada.get(f"/v1/jobs/{other['id']}", headers=key)).json()
        assert ended["error"]["message"] == f"Cancelled by ann. {kept}"
    exported = (await ada.post("/v1/models/shapes/export", headers=key)).json()
    _sql(idle, org, long_ago, 10.0, exported["id"])
    gone = (await ada.post(f"/v1/jobs/{exported['id']}/cancel", headers=key)).json()  # cancelled at once: no worker
    assert gone["state"] == "failed" and gone["error"]["message"].endswith(jobstate.KEPT["export"])


async def test_a_job_that_stops_its_worker_three_times_is_failed_lost(
    engine: AsyncEngine, ada: httpx.AsyncClient, idle: Worker, streams: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    who, key, job = await _queued(engine, ada)
    org = str(who.org_id)
    monkeypatch.setitem(protocol.CLAIM_IDLE, JOBS, 0)
    stream = protocol.kernel_stream(JOBS, idle.kernel)
    idle.loop.ensure_group()
    taken = streams.xreadgroup(GROUP, "dead", {stream: ">"}, count=1)[0][1][0][0]
    for n in range(protocol.MAX_DELIVERIES):  # each claim a worker that took it and died
        streams.xclaim(stream, GROUP, f"dead{n}", 0, [taken])
    idle.loop.one()
    lost = (await ada.get(f"/v1/jobs/{job['id']}", headers=key)).json()
    assert (lost["state"], lost["error"]) == ("failed", jobstate.LOST)
    process.lost(idle.ctx, Message(org, "shapes", "learn", {}))  # one with no job named: logged, nothing else
    idle.given_up(Message(org, "shapes", "learn", {"job": job["id"]}))  # failed already: unchanged
    sync = Worker(ADA, SYNC)
    try:
        sync.given_up(Message(org, "shapes", "decide", {}))  # a sync message: nothing to fail
    finally:
        sync.ctx.conn.close()
    assert (await ada.get(f"/v1/jobs/{job['id']}", headers=key)).json() == lost


def test_a_jobs_beat_goes_on_through_a_redis_that_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    beats: list[str] = []
    failed = threading.Event()

    def beat(_redis: Any, job_id: str) -> None:
        beats.append(job_id)
        if len(beats) == 1:
            failed.set()
            raise RedisError("down a moment")

    monkeypatch.setattr(jobstate, "beat", beat)
    monkeypatch.setitem(protocol.HEARTBEAT, JOBS, 0.01)
    with Beat(None, "j1"):  # type: ignore[arg-type]
        assert failed.wait(5)
        while len(beats) < 3:
            pass
    assert set(beats) == {"j1"}


async def test_claude_cancels_a_job_and_sees_its_stage(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, idle: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    org = str(who.org_id)
    await tool(ada, auth, "ada_model_create", name="shapes", spec=SHAPES)
    queued = data(await tool(ada, auth, "ada_learn", name="shapes"))
    cancelled = await tool(ada, auth, "ada_job_cancel", id=queued["id"])
    assert data(cancelled)["error"]["code"] == "E_CANCELLED" and "failed" in text(cancelled)
    running = data(await tool(ada, auth, "ada_learn", name="shapes"))
    _sql(
        idle,
        org,
        "UPDATE {s}.jobs SET state = 'running', started_at = now(), stage = 'learning' WHERE id = %s",
        running["id"],
    )
    assert "(learning)" in text(await tool(ada, auth, "ada_job", id=running["id"]))
    monkeypatch.setattr("glyphh_server.mcp.tools.ada_jobs.CANCEL_WAIT", 0.6)
    asked = await tool(ada, auth, "ada_job_cancel", id=running["id"])  # no worker runs it: still stopping
    assert data(asked)["stage"] == "cancelling" and "(cancelling)" in text(asked)
    assert (await refused(ada, auth, "ada_job_cancel", id="nope"))["code"] == "E_JOB_MISSING"


async def test_a_learn_shows_its_stage_and_ends_done(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=30)
    job = (await ada.post("/v1/models/shapes/learn", headers=key)).json()
    done = await finished(ada, key, job)
    assert (done["state"], done["percent"], done["stage"]) == ("done", 100, None)
