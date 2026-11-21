"""Every read of a model shows on its dashboard the moment it is counted, whichever way it comes (a key, the
platform's sign-in, rrotor's /v1/runs shape, the connector's tools), and a backtest is not a read; the dashboard holds
for any model the spec allows: one output of two outcomes or of 77, two named outputs, asking by cost or by
confidence, no decides at all, a clearance it cannot fully see, and a model too big to count on every page load."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import dashboard, days
from glyphh_ada.api import meter
from glyphh_ada.process import Worker
from glyphh_server.db import tenancy
from glyphh_server.models import AdaModelDay
from glyphh_server.ops import tend
from glyphh_server.ops.link.hub import Hub
from tests.ada.conftest import ADA, SHAPES, a_model, an_org, cases, finished, key_for, shape
from tests.ada.mcp import signed_in, tool
from tests.ada.test_dashboard import TWO, _decided
from tests.ada.test_outputs import MULTI
from tests.conftest import REDIS_URL
from tests.db.helpers import person

NONE = {"decide": 0, "query": 0, "probabilities": 0, "facts": 0, "beam": 0}


@pytest.fixture
async def counts() -> AsyncIterator[Redis]:
    client = Redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


async def _stats(ada: httpx.AsyncClient, key: dict[str, str], name: str = "shapes", n: int = 30) -> dict[str, Any]:
    got = await ada.get(f"/v1/models/{name}/stats?days={n}", headers=key)
    assert got.status_code == 200, got.text
    return dict(got.json())


async def test_every_way_a_read_comes_counts_on_the_dashboard_and_a_backtest_does_not(
    engine: AsyncEngine,
    ada: httpx.AsyncClient,
    worker: Worker,
    jobs_worker: Worker,
    counts: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unlimited(*_: Any) -> None:  # Free's 5 calls a second, out of the way of a test's quick calls
        return None

    monkeypatch.setattr(meter, "_rate", unlimited)
    who = await person(engine, "Free")  # the org in the report: Free, its dashboard read through the platform
    session, key, connector = who.headers, await key_for(ada, who), await signed_in(engine, who)
    await a_model(ada, session, n=30)
    ask = {"data": shape(1, "r", 2)}
    platform = await ada.post("/v1/decide", json={"model": "shapes", **ask}, headers=session)  # the Try it tab
    assert platform.status_code == 200, platform.text
    for op in ("decide", "query", "probabilities", "facts"):
        assert (await ada.post(f"/v1/models/shapes/{op}", json=ask, headers=key)).status_code == 200
    for op in ("decide", "query"):
        run = await ada.post("/v1/runs", json={"model": "shapes", "function": op, "inputs": ask}, headers=key)
        assert run.status_code == 200, run.text
    for op in ("decide", "query", "probabilities", "facts"):
        await tool(ada, connector, f"ada_{op}", name="shapes", **ask)
    job = await ada.post("/v1/models/shapes/backtest", json={"candidates": [{"settings": {"k": 3}}]}, headers=key)
    assert (await finished(ada, key, job.json()))["state"] == "done"
    await _decided(counts, who.org_id, 4)
    got = await _stats(ada, session)  # before the minute tick: what Redis holds shows at once
    today = got["days"][-1]
    assert today["reads"] == {"decide": 4, "query": 3, "probabilities": 2, "facts": 2, "beam": 0}
    assert today["decided"] == 4 and sum(got["sure"]) == 4 and got["answers"][0]["decided"] == 4
    assert all(d["reads"] == NONE for d in got["days"][:-1]) and len(got["days"]) == 30
    assert (await ada.get("/v1/usage", headers=key)).json()["requests"]["used"] == 11  # the backtest read nothing
    await days.flush(engine, counts)
    assert (await _stats(ada, session))["days"] == got["days"]  # the tick's, the same


async def test_days_before_the_model_was_made_are_empty_and_another_models_are_not_its(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, counts: Redis
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key)
    today = datetime.now(UTC).date()
    async with engine.begin() as conn:  # a model of the same name, deleted, read three days ago
        await tenancy.enter(conn, who.org_id)
        row = {"org_id": who.org_id, "model": "shapes", "day": today - timedelta(days=3), "metric": "read:query"}
        await conn.execute(insert(AdaModelDay).values(**row, n=5))
    early = days.field("shapes", "read:facts", (today - timedelta(days=2)).isoformat())
    await counts.hset(days.key(who.org_id), mapping={early: 7, days.field("other", "read:facts"): 9})
    await counts.sadd(days.ORGS, str(who.org_id))
    got = await _stats(ada, key, n=7)
    assert len(got["days"]) == 7 and all(d["reads"] == NONE for d in got["days"])
    assert got["days"][0]["day"] == (today - timedelta(days=6)).isoformat() and got["answers"] == []


async def test_one_output_of_77_outcomes_shows_the_most_common_and_the_rest_together(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, counts: Redis
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key)
    many = [{**c, "outcome": f"intent-{i % 77}"} for i, c in enumerate(cases(80))]
    assert (await ada.post("/v1/models/shapes/record_many", json={"cases": many}, headers=key)).status_code == 200
    assert (await ada.post("/v1/decide", json={"model": "shapes", "data": shape(3)}, headers=key)).status_code == 200
    await _decided(counts, who.org_id, 1)
    got = await _stats(ada, key)
    assert len(got["outcomes"]) == dashboard.OUTCOMES_MAX and {o["output"] for o in got["outcomes"]} == {None}
    assert got["outcomes"][0]["n"] == 2 and got["others"] == [{"output": None, "values": 27, "n": 27}]
    assert sum(o["n"] for o in got["outcomes"]) + got["others"][0]["n"] == 80
    assert [a["output"] for a in got["answers"]] == [None] and got["answers"][0]["decided"] == 1


def _ticket(i: int) -> dict[str, Any]:
    team = "billing" if i % 2 else "tech"
    words = {"billing": "refund invoice", "tech": "login error"}[team]
    data = {"t": {"w": {"product": "app" if i % 3 else "web", "text": words, "ref": f"r{i}"}}}
    return {"data": data, "outcomes": {"team": team, "urgent": "yes" if i % 5 == 0 else "no"}}


async def test_two_named_outputs_each_show_their_own_decides_and_outcomes(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, counts: Redis
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key, "tickets", spec=MULTI)
    recorded = await ada.post(
        "/v1/models/tickets/record_many", json={"cases": [_ticket(i) for i in range(20)]}, headers=key
    )
    assert recorded.status_code == 200, recorded.text
    data = {"t": {"w": {"product": "app", "text": "refund please"}}}
    both = await ada.post("/v1/models/tickets/decide", json={"data": data, "outputs": ["team", "urgent"]}, headers=key)
    one = await ada.post("/v1/models/tickets/decide", json={"data": data, "output": "team"}, headers=key)
    assert both.status_code == one.status_code == 200, both.text
    await _decided(counts, who.org_id, 3)
    got = await _stats(ada, key, "tickets")
    assert [(a["output"], a["decided"]) for a in got["answers"]] == [("team", 2), ("urgent", 1)]
    assert got["days"][-1]["decided"] == 3 and got["days"][-1]["reads"]["decide"] == 3
    assert got["sure"] == [sum(a["sure"][t] for a in got["answers"]) for t in range(10)]
    named = {(o["output"], o["value"]) for o in got["outcomes"] if o["output"]}
    assert named == {("team", "billing"), ("team", "tech"), ("urgent", "yes"), ("urgent", "no")}
    assert got["others"] == []


@pytest.mark.parametrize(
    "output",
    [{"costs": {"good": {"bad": 1}, "bad": {"good": 5}}, "ask": 0.05}, {"ask_below": 0.99}],
    ids=["by cost", "by confidence"],
)
async def test_asking_a_person_counts_however_the_output_asks(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, counts: Redis, output: dict[str, Any]
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key, spec={**SHAPES, "output": output}, n=40)
    asked = 0
    for i in range(6):
        answer = await ada.post("/v1/decide", json={"model": "shapes", "data": shape(i, "rgbk"[i % 4], i)}, headers=key)
        asked += answer.json()["ask"]
    await _decided(counts, who.org_id, 6)
    got = await _stats(ada, key)
    assert asked and got["answers"][0]["asked"] == got["days"][-1]["asked"] == asked


async def test_a_model_with_no_decides_shows_its_other_reads_and_nothing_decided(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=10)
    for op in ("query", "facts"):
        assert (await ada.post(f"/v1/models/shapes/{op}", json={"data": shape(1)}, headers=key)).status_code == 200
    got = await _stats(ada, key)
    assert got["days"][-1]["reads"] == {**NONE, "query": 1, "facts": 1} and got["days"][-1]["decided"] == 0
    assert (got["answers"], got["sure"]) == ([], [0] * 10)


async def test_a_lower_clearance_sees_the_dashboard_of_a_model_it_cannot_map(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    await a_model(ada, key, "hidden", spec={**TWO, "name": "hidden", "security_weight": 0.9})
    low = await key_for(ada, who, 0.5)
    assert (await ada.get("/v1/models/hidden/map", headers=low)).status_code == 422
    got = await _stats(ada, low, "hidden")
    assert got["precedents"] == 0 and got["answers"] == []


async def test_a_big_model_is_estimated_from_a_sample(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, key = await an_org(engine, ada)
    await a_model(ada, key, n=60)
    monkeypatch.setattr(dashboard, "EXACT_MAX", 50)
    monkeypatch.setattr(dashboard, "SAMPLE", 60)  # every block, so the estimate is the count
    got = await _stats(ada, key)
    assert got["estimated"] is True and got["precedents"] == 60
    assert sum(o["n"] for o in got["outcomes"]) == sum(g["n"] for g in got["growth"]) == 60
    monkeypatch.undo()
    assert dashboard._sampled("x{sample}", 1_000_000) == ("x TABLESAMPLE SYSTEM (2.000000) REPEATABLE (7)", 50.0)


async def test_a_tick_part_that_fails_does_not_stop_the_days_reaching_the_database(
    engine: AsyncEngine, counts: Redis, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    who = await person(engine, "Team")
    await days.count(counts.pipeline(), who.org_id, "m", "query", 2).execute()

    async def fails(*_: Any) -> None:
        raise RuntimeError("grants hiccup")

    monkeypatch.setattr(tend, "expire", fails)
    with pytest.raises(RuntimeError, match="grants hiccup"):
        await tend.tend(engine, Hub(counts), ADA, 60, None)
    assert "tick part failed: enterprise grants" in caplog.text
    assert await counts.hgetall(days.key(who.org_id)) == {}
    async with engine.begin() as conn:
        await tenancy.enter(conn, who.org_id)
        held = await days.daily(conn, counts, who.org_id, "m", datetime.now(UTC).date())
    assert held == {datetime.now(UTC).date(): {"read:query": 2}}
    assert str(uuid.UUID(str(who.org_id))) not in await counts.smembers(days.ORGS)
