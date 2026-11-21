"""Backtests: the active version and candidates scored on the model's own held-out precedents, as a job, the live
version untouched; and deletion: a model's every store gone at once, an org's whole schema gone with the org."""

import uuid
from urllib.parse import parse_qs, urlsplit

import httpx
import psycopg
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import pg
from glyphh_ada.process import Worker
from tests.ada.conftest import SHAPES, a_model, an_org, finished, shape
from tests.conftest import DATABASE_URL

PRICED = {**SHAPES, "output": {"costs": {"good": {"bad": 1}, "bad": {"good": 5}}, "ask": 0.4}}


async def test_candidates_are_scored_on_held_out_precedents(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=120, spec=PRICED)
    await ada.patch("/v1/models/shapes/settings", json={"changes": {"k": 9}}, headers=key)
    candidates = [
        {"settings": {"k": 3}, "name": "fewer"},
        {"spec_version": 1},
        {"spec": {**PRICED, "seed": 2}},
        {"spec": {"name": "broken"}},
        {"settings": {"k": 0}},
    ]
    body = {"candidates": candidates, "holdout": {"newest": 30}}
    started = await ada.post("/v1/models/shapes/backtest", json=body, headers=key)
    assert started.status_code == 202, started.text
    done = await finished(ada, key, started.json())
    assert done["state"] == "done", done
    result = done["result"]
    assert (result["version"], result["held_out"], result["trained"]) == (2, 30, 90)
    active = result["active"]
    assert active["n"] == 30 and 0 <= active["accuracy"] <= 1 and "cost_mean" in active and active["learn"] is True
    assert set(active) >= {"top_accuracy", "log_loss", "ask_rate", "accuracy_answered", "coverage", "calibration_error"}
    fewer, first, seeded, broken, zero = result["candidates"]
    assert fewer["candidate"]["name"] == "fewer" and "accuracy" in fewer["change"]
    assert first["n"] == 30 and seeded["n"] == 30
    assert broken["error"]["code"] == "E_SPEC" and zero["error"]["code"] == "E_SPEC"
    assert await _version(ada, key) == 2  # the live version untouched
    fraction = {"candidates": [], "holdout": {"fraction": 0.25, "seed": 3}, "output": "default"}
    split = await finished(ada, key, (await ada.post("/v1/models/shapes/backtest", json=fraction, headers=key)).json())
    assert split["result"]["held_out"] == 30
    nothing = {"candidates": [], "output": "none"}
    empty = await finished(ada, key, (await ada.post("/v1/models/shapes/backtest", json=nothing, headers=key)).json())
    assert empty["error"]["code"] == "E_BACKTEST"
    await a_model(ada, key, "few", n=12)
    few = {"candidates": [], "holdout": {"newest": 5}}
    small = await finished(ada, key, (await ada.post("/v1/models/few/backtest", json=few, headers=key)).json())
    assert "at least 10" in small["result"]["active"]["learn"]  # seven to learn from: it reads them unlearned
    many = await ada.post("/v1/models/shapes/backtest", json={"candidates": [{"spec_version": 1}] * 11}, headers=key)
    both = await ada.post(
        "/v1/models/shapes/backtest", json={"candidates": [{"spec_version": 1, "settings": {}}]}, headers=key
    )
    assert many.status_code == 422 and both.status_code == 422


async def _version(ada: httpx.AsyncClient, key: dict[str, str]) -> int:
    return int((await ada.get("/v1/models/shapes", headers=key)).json()["version"])


def _schema_exists(org: uuid.UUID) -> bool:
    with psycopg.connect(pg.libpq_url(DATABASE_URL), autocommit=True) as conn:
        found = conn.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (pg.schema_for(str(org)),))
        return found.fetchone() is not None


async def test_a_model_and_an_org_are_deleted_at_once(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    alice, a_key = await an_org(engine, ada)
    bob, b_key = await an_org(engine, ada)
    await a_model(ada, b_key, n=20)
    moved = (await ada.put("/v1/models/shapes/spec", json={"spec": {**SHAPES, "seed": 9}}, headers=b_key)).json()
    await finished(ada, b_key, moved["job"])
    with psycopg.connect(pg.libpq_url(DATABASE_URL), autocommit=True) as conn:
        pg.enter(conn, str(bob.org_id))
        schema = pg.schema_for(str(bob.org_id))
        assert conn.execute(f'SELECT count(DISTINCT model) FROM "{schema}".counts').fetchone()[0] == 2
        assert (await ada.delete("/v1/models/shapes?confirm=shapes", headers=b_key)).status_code == 200
        assert conn.execute(f'SELECT count(*) FROM "{schema}".counts').fetchone()[0] == 0
        assert conn.execute(f'SELECT count(*) FROM "{schema}".precedents').fetchone()[0] == 0
        assert conn.execute(f'SELECT count(*) FROM "{schema}".spec_versions').fetchone()[0] == 0
    await a_model(ada, b_key, n=5, spec={**SHAPES, "settings": {"exact_below": 0}})  # shortlisted: kept in a cache
    assert (await ada.post("/v1/models/shapes/query", json={"data": shape(1)}, headers=b_key)).status_code == 200
    made = await ada.post("http://api.test/v1/org/invites", json={"email": bob.email}, headers=alice.headers)
    token = parse_qs(urlsplit(made.json()["link"]).query)["invite"][0]
    joined = await ada.post("http://api.test/v1/invites/accept", json={"token": token}, headers=bob.headers)
    assert joined.status_code == 200, joined.text
    assert not _schema_exists(bob.org_id)
    gone = await ada.post("/v1/models/shapes/query", json={"data": shape(1)}, headers=b_key)
    assert (gone.status_code, gone.json()["error"]["code"]) == (404, "E_MODEL_MISSING")
    assert not _schema_exists(alice.org_id) and a_key  # alice never made a model
