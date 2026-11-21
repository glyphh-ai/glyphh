"""What a request and a spec may be: bodies, cases, NUL characters, the spec's bounds, few-role reads on big models,
named outputs, and writes made once under an Idempotency-Key."""

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import limits, writes
from glyphh_ada.errors import Refusal
from glyphh_ada.process import Worker
from tests.ada.conftest import SHAPES, a_model, an_org, cases, shape


async def test_bodies_cases_and_nul_are_bounded(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key)
    big = {"data": {"a": {"s": {"color": "x" * limits.BODY_MAX}}}}
    assert (await ada.post("/v1/models/shapes/query", json=big, headers=key)).status_code == 413
    told = await ada.post("/v1/models/shapes/query", content=b"{}", headers={**key, "content-length": "99999999"})
    assert told.status_code == 413
    many = await ada.post("/v1/models/shapes/record_many", json={"cases": cases(1001)}, headers=key)
    assert many.status_code == 422
    with pytest.raises(Refusal, match="at most 1000"):
        writes.record_many(None, {"cases": [{}] * 1001})  # type: ignore[arg-type]
    nul = await ada.post("/v1/models/shapes/record", json={"data": {"a": {"s": {"color": "r\u0000"}}}}, headers=key)
    assert (nul.status_code, nul.json()["error"]["reason"]) == (400, "nul")
    in_list = await ada.post("/v1/models/shapes/record_many", json={"cases": [{"data": {"\u0000": []}}]}, headers=key)
    assert in_list.status_code == 400
    bad = await ada.post("/v1/models/shapes/record", json={"data": {"nope": {}}}, headers=key)
    assert (bad.status_code, bad.json()["error"]["code"]) == (422, "E_SPEC")


@pytest.mark.parametrize(
    ("change", "limit"),
    [
        ({"dimension": 16384}, "dimension"),
        ({"settings": {"k": 500}}, "settings.k"),
    ],
)
async def test_a_spec_past_the_clouds_bounds_is_refused(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, change: dict[str, Any], limit: str
) -> None:
    _, key = await an_org(engine, ada)
    made = await ada.post("/v1/models", json={"name": "big", "spec": {**SHAPES, **change}}, headers=key)
    assert made.status_code == 422
    assert (made.json()["error"]["code"], made.json()["error"]["limit"]) == ("E_SPEC_LIMIT", limit)


def test_every_bound_of_a_spec_is_checked() -> None:
    import glyphh_spec

    roles = [{"name": f"r{i}"} for i in range(65)]
    wide = {**SHAPES, "layers": [{"name": "a", "segments": [{"name": "s", "roles": roles}]}]}
    with pytest.raises(Refusal, match="roles is at most 64"):
        limits.check_spec(glyphh_spec.Spec.from_json(wide))
    outputs = {f"o{i}": {"values": ["x", "y"]} for i in range(21)}
    with pytest.raises(Refusal, match="outputs is at most 20"):
        limits.check_spec(glyphh_spec.Spec.from_json({**SHAPES, "outputs": outputs}))
    values = {"o": {"values": [f"v{i}" for i in range(201)]}}
    with pytest.raises(Refusal, match="values is at most 200"):
        limits.check_spec(glyphh_spec.Spec.from_json({**SHAPES, "outputs": values}))


async def test_a_huge_spec_is_refused(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    _, key = await an_org(engine, ada)
    huge = {**SHAPES, "note": "x" * limits.SPEC_BYTES_MAX}
    made = await ada.post("/v1/models", json={"name": "huge", "spec": huge}, headers=key)
    assert (made.status_code, made.json()["error"]["code"]) == (413, "E_SPEC_LIMIT")


async def test_few_roles_on_a_big_model_are_refused(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(limits, "FEW_ROLES_ABOVE", 5)
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=10)
    few = await ada.post("/v1/models/shapes/decide", json={"data": {"a": {"s": {"color": "r"}}}}, headers=key)
    assert (few.status_code, few.json()["error"]["code"]) == (422, "E_FEW_ROLES")
    assert few.json()["error"]["roles"] == ["a.s.color", "a.s.shape", "a.s.size", "a.s.secret"]
    enough = {"data": {"a": {"s": {"color": "r", "size": 2}}}}
    assert (await ada.post("/v1/models/shapes/decide", json=enough, headers=key)).status_code == 200


async def test_named_outputs_are_decided_together(engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker) -> None:
    _, key = await an_org(engine, ada)
    spec = {**SHAPES, "outputs": {"team": {"values": ["red", "blue"]}}}
    assert (await ada.post("/v1/models", json={"name": "two", "spec": spec}, headers=key)).status_code == 201
    loaded = [{**c, "outcomes": {"team": "red" if i % 2 else "blue"}} for i, c in enumerate(cases(20))]
    assert (await ada.post("/v1/models/two/record_many", json={"cases": loaded}, headers=key)).status_code == 200
    both = await ada.post("/v1/decide", json={"model": "two", "data": shape(1), "outputs": ["team"]}, headers=key)
    assert set(both.json()["outputs"]) == {"team"} and both.json()["version"] == 1
    team = await ada.post("/v1/models/two/query", json={"data": shape(1), "output": "team"}, headers=key)
    assert team.json()["top"] in ("red", "blue")


async def test_a_write_is_made_once_per_idempotency_key(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key)
    once = {**key, "idempotency-key": "load-1"}
    first = await ada.post("/v1/models/shapes/record_many", json={"cases": cases(5)}, headers=once)
    again = await ada.post("/v1/models/shapes/record_many", json={"cases": cases(5)}, headers=once)
    assert first.json() == again.json() and first.json()["added"] == 5
    other = await ada.post("/v1/models/shapes/record_many", json={"cases": cases(6)}, headers=once)
    assert (other.status_code, other.json()["error"]["code"]) == (409, "E_IDEMPOTENCY")
    no_key = {**key, "idempotency-key": "k" * 201}
    assert (await ada.post("/v1/models/shapes/record", json={"data": shape(1)}, headers=no_key)).status_code == 400
    assert (await ada.get("/v1/models/shapes", headers=key)).json()["precedents"] == 5
