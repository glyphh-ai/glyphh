"""A model's dashboard, 3D view and one precedent (api/dashboard.py): its days counted where reads are counted and by
the worker after a decide has its answer, taken by the minute tick into ada_model_days; its store's outcomes, growth
and jobs; a sample of its glyphs with their nearest; each cut to the caller's clearance. None is counted as a read."""

import asyncio
import base64
import uuid
from collections.abc import AsyncIterator
from typing import Any

import glyphh_spec
import httpx
import numpy as np
import pytest
from redis import Redis as SyncRedis
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import days, glyphmap, seen
from glyphh_ada.process import Worker
from tests.ada.conftest import a_model, an_org, cases, key_for, shape
from tests.conftest import REDIS_URL

TWO: dict[str, Any] = {
    "name": "two",
    "seed": 3,
    "dimension": 1024,
    "layers": [
        {
            "name": "a",
            "segments": [
                {
                    "name": "s",
                    "roles": [
                        {"name": "color"},
                        {"name": "size", "numeric_config": {"min_value": 0, "max_value": 10, "bin_width": 1}},
                        {"name": "secret", "security_weight": 0.9},
                        {"name": "id", "key_part": True, "similarity_weight": 0},
                    ],
                }
            ],
        },
        {"name": "b", "segments": [{"name": "t", "roles": [{"name": "tag"}]}]},
    ],
    "interactions": [
        {"name": "cs", "roles": ["a.s.color", "a.s.secret"]},
        {"name": "cz", "roles": ["a.s.color", "a.s.size"]},
    ],
    "outputs": {"team": {"values": ["x", "y"]}},
}


def two(i: int) -> dict[str, Any]:
    data: dict[str, Any] = {"a": {"s": {"color": "rg"[i % 2], "size": i % 9, "secret": f"s{i % 3}", "id": f"c{i}"}}}
    if i % 4:
        data["b"] = {"t": {"tag": f"t{i % 2}"}}
    return {"data": data, "outcomes": {"team": "xy"[i % 2]}}


@pytest.fixture
async def counts() -> AsyncIterator[Redis]:
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


async def _decided(counts: Redis, org: uuid.UUID, n: int) -> None:
    """Until the worker has counted n decides (it counts after it replies)."""
    for _ in range(100):
        held = await counts.hgetall(days.key(org))
        if sum(int(v) for k, v in held.items() if k.endswith("|decided")) >= n:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"never counted {n} decides: {held}")


async def test_the_dashboard_counts_the_days_and_reads_the_store(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, counts: Redis
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key)
    empty = await ada.get("/v1/models/shapes/stats", headers=key)
    assert empty.status_code == 200, empty.text
    got = empty.json()
    assert (got["precedents"], got["outcomes"], got["growth"], got["sure"]) == (0, [], [], [0] * 10)
    none = {"decide": 0, "query": 0, "probabilities": 0, "facts": 0}
    assert len(got["days"]) == 1 and got["days"][0]["reads"] == none
    assert got["plan"] == {"plan": "Team", "precedents": {"used": 0, "max": 1_000_000}}
    assert got["active"]["version"] == 1 and got["active"]["note"] == "made" and got["jobs"] == []
    await ada.post("/v1/models/shapes/record_many", json={"cases": cases(30)}, headers=key)
    ask = {"data": shape(1, "r", 2)}
    for _ in range(3):
        assert (await ada.post("/v1/decide", json={"model": "shapes", **ask}, headers=key)).status_code == 200
    await ada.post("/v1/models/shapes/query", json=ask, headers=key)
    await ada.post("/v1/models/shapes/learn", headers=key)
    await _decided(counts, who.org_id, 3)
    assert await days.flush(engine, counts) >= 3
    got = (await ada.get("/v1/models/shapes/stats?days=7", headers=key)).json()
    today = got["days"][-1]
    assert today["reads"] == {"decide": 3, "query": 1, "probabilities": 0, "facts": 0}
    assert today["decided"] == 3 and sum(got["sure"]) == 3 and today["asked"] <= 3
    assert got["precedents"] == 30 and sum(o["n"] for o in got["outcomes"]) == 30
    assert {o["value"] for o in got["outcomes"]} == {"good", "bad"} and got["outcomes"][0]["output"] is None
    assert sum(g["n"] for g in got["growth"]) == 30
    assert [j["kind"] for j in got["jobs"]] == ["learn"]
    used = (await ada.get("/v1/usage", headers=key)).json()
    assert used["requests"]["used"] == 4  # the dashboard, the map and a precedent are not reads
    assert (await ada.get("/v1/models/nope/stats", headers=key)).status_code == 404


async def test_the_map_samples_glyphs_with_their_nearest(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key)
    empty = (await ada.get("/v1/models/shapes/map", headers=key)).json()
    assert (empty["points"], empty["edges"], empty["total"], empty["layers"]) == ([], [], 0, ["a"])
    await ada.post("/v1/models/shapes/record_many", json={"cases": cases(40)}, headers=key)
    got = (await ada.get("/v1/models/shapes/map", headers=key)).json()
    assert len(got["points"]) == 40 and got["dim"] == 2048 and got["total"] == 40
    point = got["points"][0]
    assert point["outcome"] in ("good", "bad") and point["outcomes"] == {}
    assert len(base64.b64decode(point["bits"])) == 2048 // 8
    assert got["edges"] and all(i < j and 0 < s <= 1 for i, j, s in got["edges"])
    layer = (await ada.get("/v1/models/shapes/map?layer=a&limit=10", headers=key)).json()
    assert layer["layer"] == "a" and len(layer["points"]) <= 10
    missing = await ada.get("/v1/models/shapes/map?layer=zz", headers=key)
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "E_LAYER")
    one = (await ada.get(f"/v1/models/shapes/precedents/{point['id']}", headers=key)).json()
    assert one["id"] == point["id"] and one["outcome"] == point["outcome"] and one["situation"]["a"]["s"]["color"]
    gone = await ada.get("/v1/models/shapes/precedents/nope", headers=key)
    assert (gone.status_code, gone.json()["error"]["code"]) == (404, "E_PRECEDENT_MISSING")


async def test_a_lower_clearance_sees_less_and_layers_named_outputs_and_pairs_show(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key, "two", spec=TWO)
    done = await ada.post("/v1/models/two/record_many", json={"cases": [two(i) for i in range(12)]}, headers=key)
    assert done.status_code == 200, done.text
    full = (await ada.get("/v1/models/two/map", headers=key)).json()
    low = await key_for(ada, who, 0.5)
    cut = (await ada.get("/v1/models/two/map", headers=low)).json()
    assert full["points"][0]["outcomes"] == {"team": full["points"][0]["outcomes"]["team"]}
    assert full["points"][0]["outcome"] is None
    assert [p["bits"] for p in full["points"]] != [p["bits"] for p in cut["points"]]  # the secret role is not in it
    layer_b = (await ada.get("/v1/models/two/map?layer=b", headers=low)).json()
    assert sum(p["bits"] is None for p in layer_b["points"]) == 3  # every fourth case says nothing of layer b
    rid = full["points"][0]["id"]
    seen = (await ada.get(f"/v1/models/two/precedents/{rid}", headers=low)).json()
    assert "secret" not in seen["situation"]["a"]["s"] and list(seen["situation"]["interactions"]["pairs"]) == ["cz"]
    assert seen["outcomes"] == full["points"][0]["outcomes"]
    whole = (await ada.get(f"/v1/models/two/precedents/{rid}", headers=key)).json()
    assert set(whole["situation"]["interactions"]["pairs"]) == {"cs", "cz"} and whole["situation"]["a"]["s"]["secret"]
    stats = (await ada.get("/v1/models/two/stats", headers=key)).json()
    assert {(o["output"], o["value"]) for o in stats["outcomes"]} == {(None, None), ("team", "x"), ("team", "y")}
    secret = {**TWO, "name": "hidden", "security_weight": 0.9}
    await a_model(ada, key, "hidden", spec=secret)
    for path in ("map", "precedents/x"):
        refused = await ada.get(f"/v1/models/hidden/{path}", headers=low)
        assert (refused.status_code, refused.json()["error"]["code"]) == (422, "E_SPEC")


def test_a_part_with_nothing_left_to_see_goes() -> None:
    spec = glyphh_spec.Spec.from_json(TWO)
    hidden = {"a": {"s": {"secret": "s1"}}, "interactions": {"pairs": {"cs": "r|s1"}}, "b": {"t": {"tag": "t1"}}}
    assert seen.visible(spec, hidden, 0.5) == {"b": {"t": {"tag": "t1"}}}


def test_neighbours_join_only_what_shares_bits() -> None:
    assert glyphmap.neighbours(np.zeros((1, 8), dtype=np.uint8)) == []
    bits = np.array([[1, 1, 0, 0], [1, 0, 0, 0], [0, 0, 1, 1], [0, 0, 0, 0]], dtype=np.uint8)
    assert glyphmap.neighbours(bits, k=1) == [[0, 1, 0.5]]


async def test_the_days_go_back_to_redis_when_the_database_fails(
    engine: AsyncEngine, counts: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    org = str(uuid.uuid4())  # an org that is gone: its counts are dropped
    await days.count(counts.pipeline(), org, "m", "query", 2).execute()
    await counts.hset(days.key(org), days.field("m", "read:facts"), 0)  # nothing to add
    await days.flush(engine, counts)
    assert await counts.hgetall(days.key(org)) == {}
    sync = SyncRedis.from_url(REDIS_URL, decode_responses=True)
    days.decided(sync, org, "m", {"outputs": {"a": {"ask": True, "outcome": None, "probabilities": {}}}})
    sync.close()
    assert await counts.hget(days.key(org), days.field("m", "asked")) == "1"

    async def down(*_: Any) -> bool:
        raise RuntimeError("the database is down")

    monkeypatch.setattr(days, "_add", down)
    with pytest.raises(RuntimeError):
        await days.flush(engine, counts)
    assert await counts.hget(days.key(org), days.field("m", "decided")) == "1"
    assert org in await counts.smembers(days.ORGS)
    monkeypatch.undo()
    await days.flush(engine, counts)
