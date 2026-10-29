"""A model with named outputs and a text role through steps 3 and 4: a CSV whose columns are outcomes of named outputs,
learning, a backtest of one output, an export imported again (JSONL and SQLite) answering the same, and a re-encode
that carries every named outcome into the new store."""

import base64
import io
import zipfile
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import prepare
from glyphh_ada.api.cases import Case, Grade
from glyphh_ada.process import Worker
from tests.ada.conftest import a_model, an_org, finished, path_of

MULTI: dict[str, Any] = {
    "name": "tickets",
    "seed": 4,
    "dimension": 1024,
    "layers": [
        {
            "name": "t",
            "segments": [
                {
                    "name": "w",
                    "roles": [
                        {"name": "product"},
                        {"name": "text", "text_encoding": "bag_of_words"},
                        {"name": "ref", "key_part": True, "similarity_weight": 0},
                    ],
                }
            ],
        }
    ],
    "outputs": {"team": {"values": ["billing", "tech"]}, "urgent": {"values": ["yes", "no"]}},
    "settings": {"rare": 1},
}
WORDS = {"billing": ["refund", "charge", "invoice"], "tech": ["crash", "login", "error"]}


def _row(i: int) -> str:
    team = "billing" if i % 2 else "tech"
    words = " ".join(WORDS[team][j % 3] for j in range(i % 3 + 1))
    return f"{'app' if i % 3 else 'web'},{words} please,r{i},{team},{'yes' if i % 5 == 0 else 'no'}"


def _asks() -> list[dict[str, Any]]:
    return [{"t": {"w": {"product": p, "text": t}}} for p in ("app", "web") for t in ("refund now", "login error")]


async def _answers(ada: httpx.AsyncClient, key: dict[str, str], name: str) -> list[Any]:
    asks = [{"data": d, "outputs": ["team", "urgent"]} for d in _asks()]
    return [(await ada.post(f"/v1/models/{name}/decide", json=a, headers=key)).json() for a in asks]


async def _round_trip(ada: httpx.AsyncClient, key: dict[str, str], fmt: str, into: str) -> dict[str, Any]:
    done = await finished(
        ada, key, (await ada.post("/v1/models/tickets/export", json={"format": fmt}, headers=key)).json()
    )
    data = (await ada.get(path_of(done["download"]["url"]))).content
    await a_model(ada, key, into, spec=MULTI)
    body = {"format": fmt, "content_base64": base64.b64encode(data).decode()}
    return await finished(ada, key, (await ada.post(f"/v1/models/{into}/imports", json=body, headers=key)).json())


async def test_named_outputs_go_in_out_and_through_a_reencode(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, jobs_worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, "tickets", spec=MULTI)
    lines = ["product,text,ref,team,urgent"] + [_row(i) for i in range(60)] + ["app,hello,r999,sales,no"]
    mapping = {
        "team": "outcome.team",
        "urgent": "outcome.urgent",
        "product": "t.w.product",
        "text": "t.w.text",
        "ref": "t.w.ref",
    }
    body = {"format": "csv", "mapping": mapping, "content": "\n".join(lines)}
    loaded = await finished(ada, key, (await ada.post("/v1/models/tickets/imports", json=body, headers=key)).json())
    assert (loaded["result"]["recorded"], loaded["result"]["refused"]) == (60, 1), loaded
    assert "E_OUTPUT_VALUE" in loaded["result"]["refusals"][0]["message"]
    assert set(loaded["result"]["learned"]["learned"]) == {"team", "urgent"}
    before = await _answers(ada, key, "tickets")
    assert before[0]["outputs"]["team"]["outcome"] == "billing"
    tested = {"candidates": [{"settings": {"k": 5}}], "output": "team", "holdout": {"newest": 12}}
    scored = await finished(ada, key, (await ada.post("/v1/models/tickets/backtest", json=tested, headers=key)).json())
    assert scored["result"]["active"]["n"] == 12 and "cost_mean" not in scored["result"]["active"]
    assert (await _round_trip(ada, key, "jsonl", "copy"))["result"]["learned"] == "kept"
    assert await _answers(ada, key, "copy") == before
    assert (await _round_trip(ada, key, "ada_sqlite", "third"))["result"]["glyphs"] == "kept"
    assert await _answers(ada, key, "third") == before
    moved = (await ada.put("/v1/models/tickets/spec", json={"spec": {**MULTI, "seed": 5}}, headers=key)).json()
    done = await finished(ada, key, moved["job"])
    assert done["state"] == "done" and done["result"]["precedents"] == 60, done
    after = await _answers(ada, key, "tickets")
    assert [a["outputs"]["team"]["outcome"] for a in after] == [b["outputs"]["team"]["outcome"] for b in before]
    zipped = await ada.post("/v1/models/tickets/export", json={"format": "jsonl"}, headers=key)
    archive = (await ada.get(path_of((await finished(ada, key, zipped.json()))["download"]["url"]))).content
    lines_out = zipfile.ZipFile(io.BytesIO(archive)).read("precedents.jsonl").decode().splitlines()
    assert sum('"team"' in line for line in lines_out) == 60


class _TypedSpec:
    """A kernel 3.15.0 spec's outcomes_in, as an import's rows meet it: a number kept as its bin, a many's list as
    its members' true/false."""

    def outcomes_in(self, named: dict[str, Any]) -> dict[str, Any]:
        return {"refund": "45", "tags--0": "true", "tags--1": "false"} if "tags" in named else named

    def check_outcome(self, output: str, value: str) -> None:
        assert value in ("45", "true", "false")


class _TypedModel:
    spec = _TypedSpec()

    def _name(self, output: str) -> str:
        return output


def test_an_imported_rows_typed_outcomes_go_through_the_kernels_outcomes_in() -> None:
    model: Any = _TypedModel()
    outcome, named = prepare._outcomes(model, {"outcomes": {"refund": 42.5, "tags": ["mobile"]}})
    assert outcome is None and named == {"refund": "45", "tags--0": "true", "tags--1": "false"}


def test_a_case_and_a_grade_take_every_kind_of_outcome() -> None:
    case = Case(data={}, outcomes={"kind": "bug", "urgent": True, "refund": 42.5, "tags": ["web", "gold"]})
    assert case.outcomes == {"kind": "bug", "urgent": True, "refund": 42.5, "tags": ["web", "gold"]}
    assert Grade(id="c1", output="tags", value=["web"]).value == ["web"]
    assert Grade(id="c1", output="refund", value=7).value == 7
