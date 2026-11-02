"""A worker's cache (cache.py, 2026-11-02): a model read whole is loaded once for a run of reads and again only when
its precedents change on any worker; the same read of an unchanged model is answered from the worker's own answers;
what it holds in memory stays under LOADED_MAX; and nothing it holds outlives the model."""

from typing import Any

import glyphh_kernel
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import cache, pg, reads
from glyphh_ada.process import Worker
from tests.ada.conftest import a_model, an_org, shape


def _counting(monkeypatch: pytest.MonkeyPatch) -> tuple[list[int], list[str]]:
    """Every time a worker reads a model's store whole, and every read it computes (not answered from its answers)."""
    loads: list[int] = []
    computed: list[str] = []
    load, read = glyphh_kernel.Space._ensure_loaded, reads.read

    def counted_load(self: glyphh_kernel.Space) -> None:
        loads.extend([] if self._loaded else [1])
        load(self)

    def counted_read(model: Any, op: str, args: dict[str, Any], clearance: float) -> Any:
        computed.append(op)
        return read(model, op, args, clearance)

    monkeypatch.setattr(glyphh_kernel.Space, "_ensure_loaded", counted_load)
    monkeypatch.setattr(reads, "read", counted_read)
    return loads, computed


async def test_a_small_model_is_loaded_once_and_again_after_a_write(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=40)
    loads, computed = _counting(monkeypatch)
    ask = {"data": shape(7, "g", 9)}
    first = (await ada.post("/v1/models/shapes/decide", json=ask, headers=key)).json()
    for i in range(5):  # other cases: computed each, on the copy loaded once
        assert (await ada.post("/v1/models/shapes/decide", json={"data": shape(i)}, headers=key)).status_code == 200
    assert len(loads) == 1 and computed == ["decide"] * 6
    assert (await ada.post("/v1/models/shapes/decide", json=ask, headers=key)).json() == first  # answered as before
    other = {**ask, "clearance": 0.5}
    assert (await ada.post("/v1/models/shapes/decide", json=other, headers=key)).status_code == 200
    assert computed == ["decide"] * 7 and len(loads) == 1
    recorded = await ada.post("/v1/models/shapes/record", json={"data": shape(900), "outcome": "good"}, headers=key)
    assert recorded.status_code == 200
    after = (await ada.post("/v1/models/shapes/decide", json=ask, headers=key)).json()
    assert computed == ["decide"] * 8 and len(loads) == 2  # the write moved the data counter: read whole again
    assert after["outcome"] == first["outcome"]


async def test_a_worker_keeps_its_last_answers_only(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=20)
    _, computed = _counting(monkeypatch)
    monkeypatch.setattr(cache, "ANSWERS", 1)
    for i in (1, 2, 1):  # the second answer pushed out the first: it is computed again
        assert (await ada.post("/v1/models/shapes/decide", json={"data": shape(i)}, headers=key)).status_code == 200
    assert computed == ["decide"] * 3


async def test_what_is_held_stays_under_loaded_max(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, key = await an_org(engine, ada)
    for name in ("a", "b", "c"):
        await a_model(ada, key, name, n=20)
    monkeypatch.setattr(cache, "LOADED_MAX", 45)
    for name in ("a", "b", "c"):
        assert (await ada.post(f"/v1/models/{name}/query", json={"data": shape(1)}, headers=key)).status_code == 200
    held = {k[1]: e.model.space.loaded for k, e in worker.ctx.models._lru.items()}
    assert held == {"b": True, "c": True}  # a went first: 60 held is past 45
    monkeypatch.setattr(cache, "LOADED_MAX", 10)
    assert (await ada.post("/v1/models/a/query", json={"data": shape(2)}, headers=key)).status_code == 200
    assert "a" not in {k[1] for k in worker.ctx.models._lru}  # 20 alone is past 10: never kept


async def test_nothing_held_outlives_the_model(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key, n=20)
    ask = {"data": shape(3)}
    assert (await ada.post("/v1/models/shapes/decide", json=ask, headers=key)).status_code == 200
    schema = pg.enter(worker.ctx.conn, str(who.org_id))
    worker.ctx.conn.execute(f'UPDATE "{schema}".models SET deleted_at = now()')  # gone, with no bump reaching here
    gone = await ada.post("/v1/models/shapes/decide", json=ask, headers=key)
    assert (gone.status_code, gone.json()["error"]["code"]) == (404, "E_MODEL_MISSING")


async def test_a_write_that_fails_leaves_nothing_held(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    """A write runs on a copy not read whole and leaves none behind, even when it is refused after the kernel ran."""
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=20)
    assert (await ada.post("/v1/models/shapes/query", json={"data": shape(1)}, headers=key)).status_code == 200
    assert [e.model.space.loaded for e in worker.ctx.models._lru.values()] == [True]
    bad = await ada.post("/v1/models/shapes/grade", json={"id": "nope", "value": "good"}, headers=key)
    assert bad.status_code == 404
    assert not any(e.model.space.loaded for e in worker.ctx.models._lru.values())
    worker.ctx.models.unload("o", "never-held")  # nothing to drop
