"""The connector's Ada tools (docs/specs/ada-cloud.md, 4.3), called as Claude calls them, signed in with Glyphh and no
key: the scripted session of step 5 (a model built from a CSV, one lever tuned by a backtest, a version made active,
a decision), every other tool, and the tools hidden while Ada Cloud is off."""

import json

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import requests
from glyphh_ada.process import Worker
from tests.ada.conftest import SHAPES, a_model, an_org, cases, key_for, path_of, shape
from tests.ada.mcp import data, refused, rpc, signed_in, text, tool
from tests.ada.test_outputs import MULTI
from tests.connector import granted
from tests.connector import rpc as api_rpc
from tests.db.helpers import person

PRICED = {**SHAPES, "output": {"costs": {"good": {"bad": 1}, "bad": {"good": 5}}, "ask": 0.4}}
MAPPING = {"Colour": "a.s.color", "Shape": "a.s.shape", "Size": "a.s.size", "Ref": "a.s.id", "Verdict": "outcome"}


def csv(n: int) -> str:
    """A person's file: a header, then n cases."""
    rows = [
        f"{c['data']['a']['s']['color']},{c['data']['a']['s']['shape']},{c['data']['a']['s']['size']},"
        f"{c['data']['a']['s']['id']},{c['outcome']}"
        for c in cases(n)
    ]
    return "\n".join(["Colour,Shape,Size,Ref,Verdict", *rows])


async def test_claude_builds_a_model_from_a_csv_tunes_it_and_decides(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    auth = await signed_in(engine, await person(engine, "Team"))
    made = await tool(ada, auth, "ada_model_create", name="shapes", spec=PRICED)
    assert data(made)["version"] == 1 and "Made shapes" in text(made)
    started = await tool(ada, auth, "ada_import", name="shapes", format="csv", mapping=MAPPING, content=csv(160))
    job = data(started)
    assert job["state"] == "queued" and "ada_job" in text(started)
    imported = data(await tool(ada, auth, "ada_job", id=job["id"], wait_seconds=50))
    assert imported["state"] == "done" and imported["result"]["recorded"] == 160, imported
    listed = await tool(ada, auth, "ada_models")
    assert text(listed) == "shapes: version 1 on ada-1-0, 160 precedents"
    # One lever, backtested first: fewer neighbours voting
    tried = data(
        await tool(
            ada,
            auth,
            "ada_backtest",
            name="shapes",
            candidates=[{"settings": {"k": 3}, "name": "k3"}, {"settings": {"k": 0}}],
        )
    )
    scored = await tool(ada, auth, "ada_job", id=tried["id"], wait_seconds=50)
    lines = text(scored).splitlines()
    assert data(scored)["state"] == "done" and lines[1].startswith("active: accuracy") and lines[2].startswith("k3:")
    assert lines[3].startswith('{"settings": {"k": 0}}: ')  # a candidate the kernel refuses says why
    levers = await tool(ada, auth, "ada_settings", name="shapes")
    assert data(levers)["settings"]["k"] != 3 and text(levers).startswith("shapes, version 1: ")
    tuned = await tool(ada, auth, "ada_settings", name="shapes", changes={"k": 3}, note="k3", backtest=tried["id"])
    assert text(tuned) == "Version 2 of shapes is active."
    back = await tool(ada, auth, "ada_activate", name="shapes", version=1)
    assert text(back) == "Version 1 of shapes is active."
    again = await tool(ada, auth, "ada_activate", name="shapes", version=2)
    assert data(again) == {"version": 2, "active": True, "job": None}
    versions = await tool(ada, auth, "ada_versions", name="shapes")
    assert text(versions).splitlines()[1].startswith("2 (active) on ada-1-0: k3, by ")
    decided = await tool(ada, auth, "ada_decide", name="shapes", data=shape(7, "r", 2))  # red and small: good
    answer = data(decided)
    assert answer["outcome"] == "good" and answer["version"] == 2 and answer["model"] == "shapes"
    assert text(decided).startswith("shapes: good (") and text(decided).endswith("Version 2.")
    assert "expected cost" in text(decided) and answer["receipts"]


async def test_every_ada_tool_answers_as_the_api_does(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    who = await person(engine, "Team")
    auth = await signed_in(engine, who)
    assert text(await tool(ada, auth, "ada_models")) == "No models yet: ada_model_create makes one."
    await tool(ada, auth, "ada_model_create", name="shapes", spec=SHAPES)
    many = {"name": "shapes", "cases": cases(60), "idempotency_key": "load-1"}
    first = await tool(ada, auth, "ada_record_many", **many)
    assert data(first)["added"] == 60 and text(first) == "60 added, 0 replaced: shapes holds 60."
    assert data(await tool(ada, auth, "ada_record_many", **many)) == data(first)  # the same key: written once
    one = data(await tool(ada, auth, "ada_record", name="shapes", data=shape(500), outcome="good"))
    assert one["precedents"] == 61
    graded = await tool(ada, auth, "ada_grade", name="shapes", id=one["id"], value="bad")
    assert text(graded) == f"Graded {one['id']}: bad."
    ungraded = await tool(ada, auth, "ada_grade", name="shapes", id=one["id"], value=None)
    assert text(ungraded).endswith("its outcome taken away.")
    assert "Forgot" in text(await tool(ada, auth, "ada_forget", name="shapes", id=one["id"]))
    model = await tool(ada, auth, "ada_model", name="shapes")
    beta = " ada-1-1-beta is available to try (beta)."
    assert text(model) == "shapes: version 1 on ada-1-0, 60 precedents." + beta and data(model)["ada"] == "ada-1-0"
    query = await tool(ada, auth, "ada_query", name="shapes", data=shape(7, "g", 9))
    assert data(query)["top"] == "good" and text(query).startswith("good at confidence")
    unsure = await tool(ada, auth, "ada_query", name="shapes", data=shape(7, "z", 9), clearance=0.1)
    assert data(unsure)["version"] == 1
    probabilities = await tool(ada, auth, "ada_probabilities", name="shapes", data=shape(7, "g", 9))
    assert text(probabilities).startswith("good ") and set(data(probabilities)["probabilities"]) == {"good", "bad"}
    facts = await tool(ada, auth, "ada_facts", name="shapes", data=shape(7, "g", 9), top=2)
    assert text(facts) == "2 fact trees, best first." and len(data(facts)["facts"]) == 2
    one_fact = await tool(ada, auth, "ada_facts", name="shapes", data=shape(7, "g", 9), top=1)
    assert text(one_fact) == "1 fact tree, best first."
    learned = data(await tool(ada, auth, "ada_learn", name="shapes"))
    assert data(await tool(ada, auth, "ada_job", id=learned["id"], wait_seconds=50))["state"] == "done"
    fitted = data(await tool(ada, auth, "ada_calibrate", name="shapes"))
    assert data(await tool(ada, auth, "ada_job", id=fitted["id"], wait_seconds=50))["state"] == "done"
    exported = data(await tool(ada, auth, "ada_export", name="shapes", format="jsonl"))
    ready = await tool(ada, auth, "ada_job", id=exported["id"], wait_seconds=50)
    url = data(ready)["download"]["url"]
    assert url.startswith("http://ada.test/v1/downloads/") and url in text(ready)
    got = await ada.get(path_of(url))
    assert got.status_code == 200 and got.headers["content-type"] == "application/zip"
    reseeded = await tool(ada, auth, "ada_spec_update", name="shapes", spec={**SHAPES, "seed": 9}, note="seed 9")
    assert "is being made by job" in text(reseeded) and data(reseeded)["active"] is False
    done = await tool(ada, auth, "ada_job", id=data(reseeded)["job"]["id"], wait_seconds=50)
    assert data(done)["state"] == "done"
    wrong = await refused(ada, auth, "ada_model_delete", name="shapes", confirm="nope")
    assert wrong["code"] == "E_CONFLICT"
    gone = await tool(ada, auth, "ada_model_delete", name="shapes", confirm="shapes")
    assert text(gone) == "Deleted shapes and every precedent it held."
    missing = await refused(ada, auth, "ada_model", name="shapes")
    assert missing["code"] == "E_MODEL_MISSING"
    await tool(ada, auth, "ada_model_create", name="tickets", spec=MULTI)
    tickets = [
        {"data": {"t": {"w": {"product": p, "text": t, "ref": f"r{n}"}}}, "outcomes": {"team": team, "urgent": "no"}}
        for n, (p, t, team) in enumerate([("app", "refund please", "billing"), ("web", "login error", "tech")] * 6)
    ]
    await tool(ada, auth, "ada_record_many", name="tickets", cases=tickets)
    month = requests.period()
    before = (await ada.get("/v1/usage", headers=await key_for(ada, who))).json()["requests"]["used"]
    both = await tool(ada, auth, "ada_decide", name="tickets", data=tickets[0]["data"], outputs=["team", "urgent"])
    said = text(both).splitlines()
    assert said[0].startswith("team: billing (") and said[1].startswith("urgent: no (") and said[2] == "Version 1."
    after = (await ada.get("/v1/usage", headers=await key_for(ada, who))).json()
    assert (after["requests"]["used"] - before, after["month"]) == (2, month)  # one request per output decided


async def test_imports_by_upload_link_and_by_rows(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    auth = await signed_in(engine, who)
    await a_model(ada, key)
    waiting = await tool(ada, auth, "ada_import", name="shapes", format="jsonl", learn=False)
    upload = data(waiting)["upload"]["url"]
    assert upload.startswith("http://ada.test/v1/uploads/") and f"curl -T <file> '{upload}'" in text(waiting)
    lines = "".join(json.dumps(c) + "\n" for c in cases(20)).encode()
    put = await ada.put(path_of(upload), content=lines)
    assert put.status_code == 202, put.text
    done = data(await tool(ada, auth, "ada_job", id=data(waiting)["id"], wait_seconds=50))
    assert done["state"] == "done" and done["result"]["recorded"] == 20
    rows = await tool(ada, auth, "ada_import", name="shapes", format="jsonl", rows=cases(30, 20), learn=False)
    assert data(rows)["state"] == "queued"
    finished = data(await tool(ada, auth, "ada_job", id=data(rows)["id"], wait_seconds=50))
    assert finished["result"]["recorded"] == 30
    bad = await refused(ada, auth, "ada_import", name="shapes", format="csv", rows=cases(1))
    assert (bad["code"], bad["reason"]) == ("E_INVALID", "rows")
    seen = await tool(ada, auth, "ada_job", id=data(waiting)["id"])  # no wait: as it stands
    assert text(seen) == f"Job {data(waiting)['id']} (import of shapes): done, 100%."
    failed = data(
        await tool(ada, auth, "ada_import", name="shapes", format="csv", mapping={"X": "a.s.nothing"}, content="X\n1")
    )
    failing = await tool(ada, auth, "ada_job", id=failed["id"], wait_seconds=50)
    assert data(failing)["state"] == "failed" and "failed" in text(failing)


async def test_api_keys_from_the_connector_call_the_ada_api(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    auth = await signed_in(engine, await person(engine, "Team"))
    assert text(await tool(ada, auth, "api_keys")) == "No API keys yet: create_api_key makes one."
    made = await tool(ada, auth, "create_api_key", name="CRM", expires_in_days=30, clearance=0.5)
    key = data(made)["key"]
    assert key.startswith("glyphh_ak_") and "http://ada.test" in text(made) and "clearance 0.5" in text(made)
    bearer = {"authorization": f"Bearer {key}"}
    assert (await ada.get("/v1/models", headers=bearer)).status_code == 200
    listed = await tool(ada, auth, "api_keys")
    assert text(listed).startswith("CRM, made ") and "revoked" not in text(listed)
    gone = await tool(ada, auth, "revoke_api_key", key_id=data(made)["id"])
    assert "revoked" in text(gone)
    assert "revoked" in text(await tool(ada, auth, "api_keys"))
    forever = await tool(ada, auth, "create_api_key", name="Script")
    assert "expires never" in text(forever)


async def test_the_ada_tools_are_there_only_with_ada_cloud_on(
    engine: AsyncEngine, client: httpx.AsyncClient, ada: httpx.AsyncClient
) -> None:
    who = await person(engine, "Team")
    _, off_auth = await granted(engine, who)
    names = {t["name"] for t in (await api_rpc(client, off_auth, "tools/list"))["result"]["tools"]}
    assert "ada_decide" not in names and "create_api_key" not in names and "whoami" in names
    hidden = await api_rpc(client, off_auth, "tools/call", name="ada_models", arguments={})
    assert hidden["error"]["message"] == "There is no tool 'ada_models'."
    off = (await api_rpc(client, off_auth, "server/discover"))["result"]["instructions"]
    assert "Ada Cloud" not in off
    auth = await signed_in(engine, who)
    on = {t["name"] for t in (await rpc(ada, auth, "tools/list"))["result"]["tools"]}
    assert {"ada_decide", "ada_import", "ada_backtest", "ada_job", "create_api_key", "whoami"} <= on
    assert "Ada Cloud" in (await rpc(ada, auth, "server/discover"))["result"]["instructions"]
