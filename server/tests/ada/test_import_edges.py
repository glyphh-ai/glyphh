"""Imports and files at their edges: rows refused for each reason (the first hundred named), ids made for a spec
without key parts, a plan without a cap, an import that goes on where a dead worker left it, the same request sent
twice, files larger than a chunk, links forged, of another kind or expired, a file gone before its download."""

import base64
import io
import json
import uuid
import zipfile
from typing import Any

import httpx
import psycopg
import pytest
from psycopg.types.json import Jsonb
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import catalog, imported, limits, links, pg
from glyphh_ada.errors import NoKey, Refusal
from glyphh_ada.handlers import handle
from glyphh_ada.process import Worker, work
from glyphh_ada.protocol import JOBS, Message
from glyphh_server.app import create_app
from tests.ada.conftest import ADA, SHAPES, a_model, an_org, cases, finished, key_for, path_of, shape
from tests.conftest import DATABASE_URL, _client
from tests.db.helpers import person

KEYLESS: dict[str, Any] = {
    **SHAPES,
    "layers": [{"name": "a", "segments": [{"name": "s", "roles": [{"name": "color"}]}]}],
}


def jsonl(rows: list[Any]) -> str:
    return "".join(json.dumps(r) + "\n" for r in rows)


async def _import(ada: httpx.AsyncClient, key: dict[str, str], body: dict[str, Any], name: str = "shapes") -> Any:
    started = await ada.post(f"/v1/models/{name}/imports", json=body, headers=key)
    assert started.status_code == 202, started.text
    return await finished(ada, key, started.json())


async def test_every_reason_a_row_is_refused(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key)
    bad = [
        {"data": shape(1), "id": True},
        {"data": shape(2), "outcome": 5},
        {"data": shape(3), "outcomes": [1]},
        {"data": shape(4), "outcomes": {"nope": "x"}},
        {"data": shape(5), "outcomes": {"nope": 5}},
        {"data": shape(6), "ts": "yesterday"},
    ] + [{"data": {}}] * 100
    done = (await _import(ada, key, {"format": "jsonl", "content": jsonl(bad)}))["result"]
    assert (done["refused"], len(done["refusals"]), done["recorded"]) == (106, 100, 0)
    paths = [r["path"] for r in done["refusals"][:6]]
    assert paths == ["id", "outcome", "outcomes", "outputs.nope", "outcomes", "ts"]
    assert done["learned"]["error"]["code"] == "E_SPEC"
    exported = io.BytesIO()
    with zipfile.ZipFile(exported, "w") as archive:
        archive.writestr("precedents.jsonl", jsonl([{"id": "x"}]))
        archive.writestr("spec.json", json.dumps([{"version": 1, "spec": SHAPES, "active": True}]))
        archive.writestr("learned.json", "{}")
    body = {"format": "jsonl", "content_base64": base64.b64encode(exported.getvalue()).decode()}
    stored = (await _import(ada, key, body))["result"]
    assert stored["refusals"][0]["path"] == "situation"


async def test_ids_made_for_a_spec_without_key_parts_and_no_cap(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "BATCH", 7)
    who = await person(engine, "Enterprise")
    key = await key_for(ada, who)
    await a_model(ada, key, "plain", spec=KEYLESS)
    rows = [{"data": {"a": {"s": {"color": c}}}, "outcome": c} for c in "rgb" * 7] + [
        {"data": {"a": {"s": {"color": "r"}}}, "id": "given", "outcome": "r"}
    ]
    done = await _import(ada, key, {"format": "jsonl", "content": jsonl(rows)}, "plain")
    assert (done["result"]["recorded"], done["result"]["added"]) == (22, 22)
    again = await _import(ada, key, {"format": "jsonl", "content": jsonl(rows)}, "plain")  # another job: new ids
    assert again["result"]["added"] == 21
    assert (await ada.get("/v1/models/plain", headers=key)).json()["precedents"] == 43


async def test_an_import_goes_on_where_its_worker_died(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key)
    started = (await ada.post("/v1/models/shapes/imports", json={"format": "jsonl"}, headers=key)).json()
    assert (await ada.put(path_of(started["upload"]["url"]), content=jsonl(cases(50)).encode())).status_code == 202
    other = Worker(ADA, JOBS)
    schema = pg.enter(other.ctx.conn, str(who.org_id))
    other.ctx.conn.execute(
        f'UPDATE "{schema}".jobs SET state = %s, result = %s WHERE id = %s',
        ("running", Jsonb({"done": 30}), started["id"]),
    )
    work(other.ctx, Message(str(who.org_id), "shapes", "import", {"job": started["id"]}))
    done = (await ada.get(f"/v1/jobs/{started['id']}", headers=key)).json()
    assert done["state"] == "done" and done["result"]["recorded"] == 20  # rows 31 to 50
    with pytest.raises(Refusal, match="No such import"):  # import_go for a job that is no import
        handle(other.ctx, Message(str(who.org_id), "other", "import_go", {"job": started["id"]}))
    again = handle(other.ctx, Message(str(who.org_id), "shapes", "import_go", {"job": started["id"]}))
    assert again[0]["state"] == "done"
    other.ctx.conn.close()


async def test_the_same_request_twice_and_files_of_many_chunks(
    engine: AsyncEngine, worker: Worker, jobs_worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "CHUNK", 1000)
    tight = ADA.model_copy(update={"ada_import_bytes": 1 << 20})
    async for ada in _client(create_app(tight)):
        ada.base_url = httpx.URL("http://ada.test")
        _, key = await an_org(engine, ada)
        await a_model(ada, key)
        body, once = {"format": "jsonl", "content": jsonl(cases(120))}, {**key, "idempotency-key": "k1"}
        first = await ada.post("/v1/models/shapes/imports", json=body, headers=once)
        assert (await finished(ada, key, first.json()))["result"]["recorded"] == 120
        second = await ada.post("/v1/models/shapes/imports", json=body, headers=once)
        assert (second.json()["id"], second.json()["state"]) == (first.json()["id"], "done")
        proxied = {**key, "x-forwarded-proto": "https"}
        started = await ada.post("/v1/models/shapes/imports", json={"format": "jsonl"}, headers=proxied)
        assert started.json()["upload"]["url"].startswith("https://ada.test/v1/uploads/")
        big = await ada.put(path_of(started.json()["upload"]["url"]), content=b"x" * ((1 << 20) + 1))
        assert big.status_code == 413
        made = await ada.post("/v1/models/shapes/export", json={"format": "jsonl"}, headers=key)
        done = await finished(ada, key, made.json())
        assert done["result"]["bytes"] > 1000
        got = await ada.get(path_of(done["download"]["url"]))
        assert len(got.content) == done["result"]["bytes"]
        org = str(done["download"]["url"])  # the link's own org, read back
        link = links.check(ADA.secret_key, path_of(org).rsplit("/", 1)[1], links.DOWN)
        with psycopg.connect(pg.libpq_url(DATABASE_URL), autocommit=True) as conn:
            pg.enter(conn, link.org)
            conn.execute(f'DELETE FROM "{pg.schema_for(link.org)}".files')
        assert (await ada.get(path_of(done["download"]["url"]))).status_code == 404


def test_links_of_another_kind_or_expired_let_nothing_through() -> None:
    made = links.Link(str(uuid.uuid4()), "m", str(uuid.uuid4()), links.UP, 100, "")
    token = links.sign("secret", made)
    assert links.check("secret", token, links.UP, now=99) == made
    with pytest.raises(NoKey, match="not for this"):
        links.check("secret", token, links.DOWN, now=99)
    with pytest.raises(NoKey, match="expired"):
        links.check("secret", token, links.UP, now=101)
    with pytest.raises(NoKey, match="not one of ours"):
        links.check("other", token, links.UP, now=99)


async def test_an_index_build_that_fails_leaves_none_behind(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    who, key = await an_org(engine, ada)
    made = await a_model(ada, key, n=3)
    with psycopg.connect(pg.libpq_url(DATABASE_URL), autocommit=True) as conn:
        schema = pg.enter(conn, str(who.org_id))
        store = catalog.store(conn, schema, made["id"].replace("-", ""), SHAPES["dimension"])
        store.drop_index()
        monkeypatch.setattr(imported, "_BUILD", imported._BUILD.replace("bit_hamming_ops", "no_such_ops"))
        with pytest.raises(psycopg.errors.UndefinedObject):
            imported.build_index(store)
        indexes = conn.execute(
            "SELECT count(*) FROM pg_indexes WHERE schemaname = %s AND indexname LIKE '%%_glyph'", (schema,)
        )
        assert indexes.fetchone()[0] == 0
        monkeypatch.undo()
        imported.build_index(store)
