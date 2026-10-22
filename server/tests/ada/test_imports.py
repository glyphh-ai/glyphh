"""Imports: a file of cases into a model as a job, by an upload link or in the body; JSON Lines and CSV with a mapping;
refused rows named and the rest recorded; the plan's cap checked for the whole file up front; the index dropped and
built again; learned once at the end."""

import base64
import json
from typing import Any

import httpx
import psycopg
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import pg
from glyphh_ada.process import Worker
from glyphh_server.app import create_app
from tests.ada.conftest import ADA, a_model, an_org, cases, finished, path_of, shape
from tests.conftest import DATABASE_URL, _client


def jsonl(rows: list[dict[str, Any]]) -> bytes:
    return "".join(json.dumps(r) + "\n" for r in rows).encode()


def _index(org: str, model_id: str) -> bool:
    with psycopg.connect(pg.libpq_url(DATABASE_URL), autocommit=True) as conn:
        pg.enter(conn, org)
        found = conn.execute(
            "SELECT count(*) FROM pg_indexes WHERE schemaname = %s AND indexdef LIKE '%%hnsw%%'"
            " AND tablename IN (SELECT c.relname FROM pg_class c WHERE c.relispartition)",
            (pg.schema_for(org),),
        )
        return bool(found.fetchone()[0])


async def test_a_jsonl_file_by_its_upload_link(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    made = await a_model(ada, key)
    started = await ada.post("/v1/models/shapes/imports", json={"format": "jsonl"}, headers=key)
    assert started.status_code == 202, started.text
    job = started.json()
    assert job["state"] == "awaiting" and job["upload"]["url"].startswith("http://ada.test/v1/uploads/")
    body = jsonl(cases(100)) + b"not json\n" + jsonl([[1, 2], {"data": {"nope": {}}}, {"data": shape(1), "x": 1}])
    assert len(body) > 8192  # read through a buffer smaller than its chunk
    sent = await ada.put(path_of(job["upload"]["url"]), content=body)
    assert sent.status_code == 202 and sent.json()["state"] == "queued", sent.text
    again = await ada.put(path_of(job["upload"]["url"]), content=body)
    assert (again.status_code, again.json()["error"]["reason"]) == (409, "import_started")
    done = await finished(ada, key, job)
    result = done["result"]
    assert done["state"] == "done", done
    assert (result["rows"], result["recorded"], result["added"], result["refused"]) == (104, 100, 100, 4)
    assert [r["row"] for r in result["refusals"]] == [101, 102, 103, 104]
    assert result["learned"]["tau"] > 0 and result["seconds"]["total"] > 0
    assert (await ada.get("/v1/models/shapes", headers=key)).json()["precedents"] == 100
    empty = (await ada.post("/v1/models/shapes/imports", json={"format": "jsonl"}, headers=key)).json()
    assert (await ada.put(path_of(empty["upload"]["url"]), content=b"")).status_code == 202
    assert (await finished(ada, key, empty))["result"]["rows"] == 0
    assert _index(str(who.org_id), made["id"].replace("-", ""))
    viewed = await ada.get(f"/v1/models/shapes/imports/{job['id']}", headers=key)
    assert viewed.json()["result"] == result
    other = await ada.get(f"/v1/models/other/imports/{job['id']}", headers=key)
    assert other.status_code == 404
    asked = (await ada.post("/v1/decide", json={"model": "shapes", "data": shape(7, "g", 9)}, headers=key)).json()
    assert asked["outcome"] == "good"


async def test_a_csv_file_in_the_body_with_a_mapping(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key)
    lines = ["Colour,Shape,Size,Secret,Ref,Verdict,When,Junk"]
    lines += [
        f"{c['data']['a']['s']['color']},{c['data']['a']['s']['shape']},{c['data']['a']['s']['size']},x;y,"
        f"{c['data']['a']['s']['id']},{c['outcome']},{1000 + n},z"
        for n, c in enumerate(cases(30))
    ]
    lines += ["r,sq,big,x,c999,good,1,z", "", ",,,,,,,"]
    mapping = {
        "Colour": "a.s.color",
        "Shape": "a.s.shape",
        "Size": "a.s.size",
        "Secret": "a.s.secret",
        "Ref": "a.s.id",
        "Verdict": "outcome",
        "When": "ts",
        "Junk": None,
    }
    body = {"format": "csv", "mapping": mapping, "content": "\n".join(lines), "learn": False}
    started = await ada.post("/v1/models/shapes/imports", json=body, headers=key)
    assert started.status_code == 202 and started.json()["state"] == "queued", started.text
    done = (await finished(ada, key, started.json()))["result"]
    assert (done["recorded"], done["refused"], done["learned"]) == (30, 1, None)
    assert done["refusals"][0] == {
        "row": 32,
        "path": "",
        "message": "a numeric column holds something that is not a number",
    }
    for aim in ("a.s.nothing", "outcome.nope"):
        bad = {**body, "mapping": {**mapping, "Junk": aim}}
        failed = await finished(ada, key, (await ada.post("/v1/models/shapes/imports", json=bad, headers=key)).json())
        assert failed["error"]["code"] == "E_MAPPING" and failed["error"]["target"] == aim


async def test_the_plans_cap_is_checked_for_the_whole_file(
    engine: AsyncEngine, worker: Worker, jobs_worker: Worker
) -> None:
    small = ADA.model_copy(update={"ada_precedent_caps": {"Team": 50}})
    async for ada in _client(create_app(small)):
        ada.base_url = httpx.URL("http://ada.test")
        _, key = await an_org(engine, ada)
        await a_model(ada, key, n=20)
        body = {"format": "jsonl", "content": jsonl(cases(60))}
        body["content"] = body["content"].decode()  # type: ignore[attr-defined]
        whole = await finished(ada, key, (await ada.post("/v1/models/shapes/imports", json=body, headers=key)).json())
        assert whole["error"]["code"] == "E_LIMIT" and (whole["error"]["used"], whole["error"]["adding"]) == (20, 40)
        assert (await ada.get("/v1/models/shapes", headers=key)).json()["precedents"] == 20
        part = {**body, "partial": True}
        done = await finished(ada, key, (await ada.post("/v1/models/shapes/imports", json=part, headers=key)).json())
        assert (done["result"]["added"], done["result"]["refused"], done["result"]["recorded"]) == (30, 10, 50)
        assert (await ada.get("/v1/models/shapes", headers=key)).json()["precedents"] == 50
        over = await ada.post("/v1/models/shapes/record", json={"data": shape(500)}, headers=key)
        assert (over.status_code, over.json()["error"]["reason"]) == (403, "precedents")
        same = await ada.post("/v1/models/shapes/record", json={"data": shape(5)}, headers=key)  # replaces: no more
        assert same.status_code == 200


async def test_imports_refuse_what_they_cannot_take(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key)
    wrong = await ada.post("/v1/models/shapes/imports", json={"format": "xml"}, headers=key)
    assert wrong.status_code == 422
    bad64 = await ada.post("/v1/models/shapes/imports", json={"format": "jsonl", "content_base64": "!!"}, headers=key)
    assert (bad64.status_code, bad64.json()["error"]["reason"]) == (400, "content_base64")
    big = {"format": "jsonl", "content": "x" * ((5 << 20) + 1)}  # within the body's bound, past the file's
    assert (await ada.post("/v1/models/shapes/imports", json=big, headers=key)).status_code == 413
    bigger = {"format": "jsonl", "content_base64": base64.b64encode(b"x" * (6 << 20)).decode()}
    assert (await ada.post("/v1/models/shapes/imports", json=bigger, headers=key)).status_code == 413
    open_one = await ada.post("/v1/models/shapes/imports", json={"format": "jsonl"}, headers=key)
    busy = await ada.post("/v1/models/shapes/imports", json={"format": "jsonl"}, headers=key)
    assert (busy.status_code, busy.json()["error"]["code"]) == (409, "E_BUSY")
    link = open_one.json()["upload"]["url"]
    forged = await ada.put(path_of(link)[:-3] + "abc", content=b"{}")
    assert forged.status_code == 401
    missing = await ada.post("/v1/models/none/imports", json={"format": "jsonl"}, headers=key)
    assert missing.status_code == 404
