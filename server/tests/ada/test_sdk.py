"""SDK 3 (PyPI `glyphh` 3.12.0, the client as customers have it) against the cloud with only its URL and key changed:
every function an Ada model has, through `POST /v1/runs`, each answer valid against the contract the SDK was built to
(contract.json: glyphh-ai/glyphh contract/, at 6c5123e), and its refusals the codes the SDK knows."""

import asyncio
import json
from collections.abc import Callable
from importlib import metadata
from pathlib import Path
from typing import Any

import glyphh
import httpx
import pytest
from jsonschema import validate
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada.api import runs
from glyphh_ada.process import Worker
from tests.ada.conftest import HOST, a_model, an_org, shape

CONTRACT: dict[str, Any] = json.loads((Path(__file__).with_name("contract.json")).read_text())
Transport = Callable[[str, str, Any, bytes | None], tuple[int, bytes]]


def transport(ada: httpx.AsyncClient, loop: asyncio.AbstractEventLoop, seen: list[Any]) -> Transport:
    """The SDK's own transport seam (3.0: method, url, headers, body -> status, body): each request sent to the app
    on the test's loop, from the SDK's thread."""

    def send(method: str, url: str, headers: Any, body: bytes | None) -> tuple[int, bytes]:
        sent = ada.request(method, url, headers=dict(headers), content=body)
        got = asyncio.run_coroutine_threadsafe(sent, loop).result(30)
        seen.append(got.json())
        return got.status_code, got.content

    return send


async def _sdk(ada: httpx.AsyncClient, key: dict[str, str], seen: list[Any]) -> glyphh.Ada:
    bearer = key["authorization"].removeprefix("Bearer ")
    return glyphh.Ada(f"http://{HOST}", bearer, transport=transport(ada, asyncio.get_running_loop(), seen))


async def test_sdk_3_works_against_the_cloud(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    assert metadata.version("glyphh") == "3.12.0"
    _, key = await an_org(engine, ada)
    await a_model(ada, key)
    seen: list[Any] = []
    client = await _sdk(ada, key, seen)
    model = client.model("shapes")
    for i in range(30):
        good = ("good", "bad")[i % 2]
        done = await asyncio.to_thread(model.record, shape(i, "rg"[i % 2], 2 + i % 2), good)
        assert done.done and done.data["precedents"] == i + 1
    query = await asyncio.to_thread(model.query, shape(100, "r", 2))
    validate(query.data, CONTRACT["answer"])
    assert query.data["top"] == "good"
    facts = await asyncio.to_thread(model.facts, shape(100, "r", 2), top=2, clearance=0.5)
    assert len(facts.data) == 2 and "secret" not in json.dumps(facts.data[0]["tree"])
    probabilities = await asyncio.to_thread(model.probabilities, shape(100, "g", 3))
    assert max(probabilities.data, key=probabilities.data.get) == "bad"
    decided = await asyncio.to_thread(model.decide, shape(100, "r", 2))
    assert decided.data["outcome"] == "good" and decided.data["receipts"]
    learned = await asyncio.to_thread(model.learn)
    assert learned.done and learned.data["tau"] > 0
    settings = await asyncio.to_thread(model.call, "settings")
    assert settings.data == {}
    listed = await asyncio.to_thread(client.models)
    assert [m["name"] for m in listed] == ["shapes"]
    for body in seen:
        if "run_id" in body:
            validate(body, CONTRACT["result"])
            assert body["status"] == "done" and body["version"] == 1


async def test_sdk_3_reads_the_clouds_refusals(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key)
    seen: list[Any] = []
    client = await _sdk(ada, key, seen)
    cases = [
        (lambda: client.model("shapes").call("start"), "E_FUNCTION_MISSING", 404),
        (lambda: client.model("nothing").call("start"), "E_MODEL_MISSING", 404),
        (lambda: client.model("nothing").query(shape(1)), "E_MODEL_MISSING", 404),
        (lambda: client.run("abc"), "E_RUN_MISSING", 404),
        (lambda: client.resume("abc", "yes"), "E_RUN_MISSING", 404),
        (lambda: client.model("shapes").learn(), "E_SPEC", 422),
    ]
    for call, code, status in cases:
        with pytest.raises(glyphh.AdaError) as refused:
            await asyncio.to_thread(call)
        assert (refused.value.code, refused.value.status) == (code, status)
    wrong = glyphh.Ada(f"http://{HOST}", "glyphh_ak_wrong", transport=transport(ada, asyncio.get_running_loop(), seen))
    with pytest.raises(glyphh.AdaError) as refused:
        await asyncio.to_thread(wrong.model("shapes").query, shape(1))
    assert (refused.value.code, refused.value.status) == ("E_AUTH", 401)
    for body in seen:
        validate(body, CONTRACT["error"])


FIXTURES: dict[str, Any] = json.loads((Path(__file__).with_name("fixtures.json")).read_text())
# The contract's cases a cloud can meet; the rest are a self-hosted runtime's (paused, clusters, its licence cap).
CLOUD_CASES = (
    "a call that is done",
    "a call that needs input, then continued",
    "a query",
    "a wrong key",
    "a model that is not there",
    "a read after a write, on another node",
)
INCIDENTS: dict[str, Any] = {
    "name": "incidents",
    "layers": [
        {
            "name": "error",
            "segments": [
                {"name": "what", "roles": [{"name": "class"}, {"name": "message", "text_encoding": "bag_of_words"}]}
            ],
        }
    ],
    "output": {"ask_below": 0.6},
}


@pytest.mark.parametrize("name", CLOUD_CASES)
async def test_the_contracts_requests_are_answered_in_its_shapes(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, name: str
) -> None:
    """Each fixture's request, as the SDK sends it, to a cloud model of the same name: the same status, and a body
    of the contract's shape. A run that would need input on rrotor is done here, answering `ask`."""
    _, key = await an_org(engine, ada)
    assert (await ada.post("/v1/models", json={"name": "incidents", "spec": INCIDENTS}, headers=key)).status_code == 201
    case = next(c for c in FIXTURES["cases"] if c["name"] == name)
    for step in (case, case.get("then")):
        if step is None or step["request"]["path"] != "/v1/runs":
            continue
        headers = {"authorization": "Bearer glyphh_ak_wrong"} if name == "a wrong key" else key
        got = await ada.post("/v1/runs", json=step["request"]["body"], headers=headers)
        assert got.status_code == step["response"]["status"]
        if got.status_code == 200:
            validate(got.json(), CONTRACT["result"])
            assert got.json()["status"] == "done"
        else:
            validate(got.json(), CONTRACT["error"])
            assert got.json()["error"]["code"] == step["response"]["body"]["error"]["code"]


async def test_a_learn_that_takes_long_answers_its_job(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(runs, "LEARN_WAIT", 0.3)
    monkeypatch.setattr(runs, "POLL", 0.1)
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=20)
    run = await ada.post("/v1/runs", json={"model": "shapes", "function": "learn"}, headers=key)
    assert run.json()["status"] == "done" and run.json()["data"]["job"]["state"] == "queued"  # no jobs worker
