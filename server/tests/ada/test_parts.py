"""A worker's parts on their own: the process group's command and its supervisor, reconnecting, jobs that skip, crash or
lose their model, the model cache, org schema migrations at start, and learning past the job's sample."""

import threading
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import cache, catalog, handlers, jobs, limits, orgschema, pg, runner, worker
from glyphh_ada.errors import Refusal
from glyphh_ada.process import Worker, work
from glyphh_ada.protocol import JOBS, SYNC, Message
from tests.ada.conftest import ADA, SHAPES, a_model, an_org, shape
from tests.conftest import SETTINGS


@pytest.fixture
def idle(streams: Redis) -> Iterator[Worker]:
    """A worker that is not serving: its parts called by the test, on its own connection."""
    made = Worker(ADA, JOBS)
    yield made
    made.ctx.conn.close()


def test_the_command_idles_with_ada_cloud_off_and_supervises_with_it_on(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(worker, "idle", lambda stop: calls.append("idle"))
    monkeypatch.setattr(worker, "supervise", lambda count, queue, stop: calls.append((count, queue)))
    monkeypatch.setattr(worker, "get_settings", lambda: SETTINGS)
    worker.main(["--queue", "sync"])
    monkeypatch.setattr(worker, "get_settings", lambda: ADA)
    worker.main(["--queue", "jobs", "--processes", "3"])
    worker.main(["--queue", "sync"])
    assert calls[:2] == ["idle", (3, "jobs")] and calls[2][0] >= 1


def test_the_supervisor_starts_again_a_worker_that_stops() -> None:
    stop = threading.Event()
    threading.Timer(6.0, stop.set).start()  # spawning a process takes a second or more on a small CI runner
    assert worker.supervise(2, SYNC, stop, target=print, every=0.05) > 2


def test_idle_waits_to_be_stopped_and_serve_runs_one_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = threading.Event()
    threading.Timer(0.1, stop.set).start()
    worker.idle(stop, every=0.01)
    served: list[str] = []

    class Fake:
        def __init__(self, settings: Any, queue: str) -> None:
            served.append(queue)

        def serve(self, stop: threading.Event) -> None:
            served.append("served")

    monkeypatch.setattr(worker, "Worker", Fake)
    monkeypatch.setattr(worker, "get_settings", lambda: ADA)
    worker.serve(JOBS)
    assert served == [JOBS, "served"]


async def test_a_broken_connection_is_made_again(engine: AsyncEngine, ada: httpx.AsyncClient, idle: Worker) -> None:
    who, _key = await an_org(engine, ada)
    idle.queue = SYNC
    idle.ctx.conn.close()
    found, _ = idle.dispatch(Message(str(who.org_id), "", "models", {}))
    assert found == [] and not idle.ctx.conn.closed


async def test_jobs_that_are_done_crash_or_lose_their_model(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, idle: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key, n=12)
    org = str(who.org_id)
    job = (await ada.post("/v1/models/shapes/calibrate", headers=key)).json()
    schema = pg.enter(idle.ctx.conn, org)
    jobs.mark(idle.ctx.conn, schema, job["id"], "done", percent=100, result={"kept": True})
    assert idle.dispatch(Message(org, "shapes", "calibrate", {"job": job["id"]})) == (None, None)
    assert jobs.view(idle.ctx.conn, schema, job["id"])["result"] == {"kept": True}
    crash = (await ada.post("/v1/models/shapes/learn", headers=key)).json()
    monkeypatch.setattr(runner, "run", lambda *_: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        work(idle.ctx, Message(org, "shapes", "learn", {"job": crash["id"]}))
    assert jobs.view(idle.ctx.conn, schema, crash["id"])["error"]["code"] == "E_INTERNAL"
    again = (await ada.post("/v1/models/shapes/learn", headers=key)).json()
    monkeypatch.setattr(runner, "run", lambda *_: (idle.ctx.conn.close(), 1 / 0))  # its connection gone with it
    with pytest.raises(ZeroDivisionError):
        work(idle.ctx, Message(org, "shapes", "learn", {"job": again["id"]}))
    monkeypatch.undo()
    idle.ctx = idle._connect()
    schema = pg.enter(idle.ctx.conn, org)
    lost = (await ada.post("/v1/models/shapes/learn", headers=key)).json()
    await ada.delete("/v1/models/shapes?confirm=shapes", headers=key)  # its jobs go with it
    assert work(idle.ctx, Message(org, "shapes", "learn", {"job": lost["id"]})) is None
    with pytest.raises(Refusal, match="No job"):
        jobs.view(idle.ctx.conn, schema, lost["id"])


async def test_the_cache_keeps_few_and_briefly(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, idle: Worker
) -> None:
    who, key = await an_org(engine, ada)
    for name in ("one", "two"):
        await a_model(ada, key, name)
    org = str(who.org_id)
    schema = pg.enter(idle.ctx.conn, org)
    models = cache.Models(idle.ctx.conn, idle.redis, size=1, ttl=60)
    first = models.get(org, schema, "one")
    assert models.get(org, schema, "one") is first
    models.get(org, schema, "two")  # the cache holds one: "one" goes
    assert models.get(org, schema, "one") is not first
    models.ttl = 0
    assert models.get(org, schema, "one") is not models.get(org, schema, "one")
    with pytest.raises(Refusal, match="No model named three"):
        models.get(org, schema, "three")


async def test_a_name_taken_twice_at_once_is_a_conflict(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, idle: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key)
    pg.enter(idle.ctx.conn, str(who.org_id))
    with pytest.raises(Refusal, match="has a model named shapes"):
        catalog.create(idle.ctx.conn, str(who.org_id), "shapes", SHAPES, "t")
    monkeypatch.setattr(handlers, "PRUNE_ONE_IN", 1)  # and a write that prunes old request keys
    assert (await ada.post("/v1/models/shapes/record", json={"data": shape(1)}, headers=key)).status_code == 200
    asked = await ada.post("/v1/models/shapes/query", json={"data": shape(1), "output": "nope"}, headers=key)
    assert asked.json()["error"]["code"] == "E_SPEC"


async def test_every_org_schema_is_migrated_at_start(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, idle: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key)
    assert orgschema.migrate_all(idle.ctx.conn) == 0
    more = "ALTER TABLE {s}.models ADD COLUMN IF NOT EXISTS note text"
    monkeypatch.setattr(orgschema, "MIGRATIONS", (*orgschema.MIGRATIONS, more))
    assert orgschema.migrate_all(idle.ctx.conn) >= 1
    assert orgschema.migrate_all(idle.ctx.conn) == 0
    assert orgschema.exists(idle.ctx.conn, str(who.org_id)) and not orgschema.exists(idle.ctx.conn, str(uuid.uuid4()))


async def test_step_3s_migration_gives_a_step_2_model_its_id_index(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, idle: Worker
) -> None:
    """A model made before step 3 has a partition keyed (model, id) alone; the migration indexes its ids, and runs
    again on a schema that has it without harm."""
    who, key = await an_org(engine, ada)
    await a_model(ada, key, n=5)
    org = str(who.org_id)
    schema = pg.enter(idle.ctx.conn, org)
    ids = f"SELECT count(*) FROM pg_indexes WHERE schemaname = '{schema}' AND indexname LIKE 'p\\_%\\_id'"
    assert idle.ctx.conn.execute(ids).fetchone()[0] == 1
    for (name,) in idle.ctx.conn.execute(ids.replace("count(*)", "indexname")).fetchall():
        idle.ctx.conn.execute(f'DROP INDEX "{schema}"."{name}"')
    idle.ctx.conn.execute(f'DELETE FROM "{schema}".ada_schema WHERE version = 2')
    assert orgschema.migrate_all(idle.ctx.conn) == 1
    assert idle.ctx.conn.execute(ids).fetchone()[0] == 1
    assert (await ada.post("/v1/models/shapes/record", json={"data": shape(1)}, headers=key)).status_code == 200


TEXT: dict[str, Any] = {
    "name": "words",
    "seed": 3,
    "dimension": 1024,
    "layers": [
        {
            "name": "m",
            "segments": [{"name": "b", "roles": [{"name": "text", "text_encoding": "bag_of_words"}, {"name": "kind"}]}],
        }
    ],
    "settings": {"rare": 1},
}


async def test_learning_past_the_sample_restates_every_precedent(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, idle: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "JOB_SAMPLE", 20)
    who, key = await an_org(engine, ada)
    assert (await ada.post("/v1/models", json={"name": "words", "spec": TEXT}, headers=key)).status_code == 201
    words = {"lost": "lost stolen card", "fx": "exchange rate currency"}
    loaded = [{"data": {"m": {"b": {"kind": "k"}}}, "outcome": "fx"}] + [  # the oldest has no words to weigh
        {"data": {"m": {"b": {"text": f"{words[o]} please {i}", "kind": "k"}}}, "outcome": o}
        for i, o in enumerate(["lost", "fx"] * 30)
    ]
    assert (await ada.post("/v1/models/words/record_many", json={"cases": loaded}, headers=key)).status_code == 200
    org = str(who.org_id)
    schema = pg.enter(idle.ctx.conn, org)
    seen: list[float] = []
    result = jobs.run(idle.ctx.conn, schema, "words", "learn", seen.append)
    assert (result["precedents"], result["sampled"]) == (61, 20)
    assert result["restated"] == 40 and seen[-1] == 90.0
    # A learn that died after the kernel kept what it learned, before every precedent was restated: when the next
    # learn learns the same, the kernel restates nothing, and the job restates them all.
    found = catalog.live(idle.ctx.conn, schema, "words")
    plain = '{"m": {"b": {"kind": "k", "text": ["card", "lost", "stolen"]}}}'
    idle.ctx.conn.execute(
        f'UPDATE "{schema}".precedents SET situation = %s WHERE seq = (SELECT min(seq) FROM "{schema}".precedents)',
        (plain,),
    )
    monkeypatch.setattr(jobs, "_tables", lambda model: "the same")
    idle.ctx.conn.execute(
        f'UPDATE "{schema}".meta SET value = %s WHERE model = %s AND key = %s', ("true", found.store, "restating")
    )
    again = jobs.run(idle.ctx.conn, schema, "words", "learn", seen.append)
    assert again["restated"] == 1
