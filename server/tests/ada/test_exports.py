"""Exports, and the way back: a model's JSONL archive and its SQLite store, fetched by a download link; either imported
into another model of the same spec answers exactly as the first does; the SQLite store opens in the kernel as a
self-hosted runtime opens it; a runtime's precedents.sqlite of another encoding is restated on the way in."""

import base64
import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import glyphh_spec
import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.process import Worker
from tests.ada.conftest import SHAPES, a_model, an_org, cases, finished, path_of, shape

ASKS: list[dict[str, Any]] = [shape(1000 + i, "rgbk"[i % 4], i % 11, ["sq", "ci", "tr"][i % 3]) for i in range(24)]


async def _answers(ada: httpx.AsyncClient, key: dict[str, str], name: str) -> list[Any]:
    out = []
    for data in ASKS:
        out.append((await ada.post(f"/v1/models/{name}/query", json={"data": data}, headers=key)).json())
        out.append((await ada.post(f"/v1/models/{name}/decide", json={"data": data}, headers=key)).json())
    return out


async def _export(ada: httpx.AsyncClient, key: dict[str, str], name: str, fmt: str) -> bytes:
    started = await ada.post(f"/v1/models/{name}/export", json={"format": fmt}, headers=key)
    assert started.status_code == 202, started.text
    done = await finished(ada, key, started.json())
    assert done["state"] == "done", done
    got = await ada.get(path_of(done["download"]["url"]))
    assert got.status_code == 200 and got.headers["content-disposition"].endswith(f'{done["result"]["filename"]}"')
    return got.content


async def _import(ada: httpx.AsyncClient, key: dict[str, str], name: str, fmt: str, data: bytes) -> dict[str, Any]:
    body = {"format": fmt, "content_base64": base64.b64encode(data).decode()}
    started = await ada.post(f"/v1/models/{name}/imports", json=body, headers=key)
    assert started.status_code == 202, started.text
    return await finished(ada, key, started.json())


async def test_an_export_imported_again_answers_the_same(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=80)
    learned = await finished(ada, key, (await ada.post("/v1/models/shapes/learn", headers=key)).json())
    assert learned["state"] == "done"
    before = await _answers(ada, key, "shapes")
    zipped = await _export(ada, key, "shapes", "jsonl")
    archive = zipfile.ZipFile(io.BytesIO(zipped))
    assert sorted(archive.namelist()) == ["learned.json", "precedents.jsonl", "spec.json"]
    assert len(archive.read("precedents.jsonl").splitlines()) == 80
    assert "tau" in json.loads(archive.read("learned.json"))
    await a_model(ada, key, "again")
    moved = await _import(ada, key, "again", "jsonl", zipped)
    assert (moved["result"]["recorded"], moved["result"]["learned"]) == (80, "kept")
    assert await _answers(ada, key, "again") == before
    await a_model(ada, key, "seeded", spec={**SHAPES, "seed": 7})  # reads its cases otherwise: learns its own
    relearned = await _import(ada, key, "seeded", "jsonl", zipped)
    assert relearned["result"]["recorded"] == 80 and relearned["result"]["learned"]["tau"] > 0
    store = await _export(ada, key, "shapes", "ada_sqlite")
    await a_model(ada, key, "third")
    merged = (await _import(ada, key, "third", "ada_sqlite", store))["result"]
    assert (merged["recorded"], merged["glyphs"], merged["learned"]) == (80, "kept", "kept")
    assert await _answers(ada, key, "third") == before
    with tempfile.TemporaryDirectory() as folder:  # the kernel opens it, as a self-hosted runtime does
        path = Path(folder) / "precedents.sqlite"
        path.write_bytes(store)
        model = glyphh_spec.Model(glyphh_spec.Spec.from_json(SHAPES), path=str(path), readonly=True)
        assert len(model) == 80
        assert [model.query(d).to_json() for d in ASKS] == before[0::2]


async def test_a_runtimes_store_of_another_encoding_is_restated(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=10)
    other = {**SHAPES, "seed": 99}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "precedents.sqlite"
        runtime = glyphh_spec.Model(glyphh_spec.Spec.from_json(other), path=str(path))
        runtime.record_many(cases(40))
        runtime.space.close()
        data = path.read_bytes()
    done = await _import(ada, key, "shapes", "ada_sqlite", data)
    assert done["state"] == "done", done
    assert (done["result"]["glyphs"], done["result"]["recorded"]) == ("encoded again", 40)
    assert (await ada.get("/v1/models/shapes", headers=key)).json()["precedents"] == 40  # ten held, replaced
    junk = await _import(ada, key, "shapes", "ada_sqlite", b"not a database at all" * 10)
    assert junk["error"]["code"] == "E_IMPORT"
    wide = {**SHAPES, "dimension": 1024}
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "precedents.sqlite"
        runtime = glyphh_spec.Model(glyphh_spec.Spec.from_json(wide), path=str(path))
        runtime.record_many(cases(3))
        runtime.space.close()
        refused = await _import(ada, key, "shapes", "ada_sqlite", path.read_bytes())
    assert (refused["error"]["code"], refused["error"]["reason"]) == ("E_IMPORT", "dimension")
