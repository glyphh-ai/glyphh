"""Ada Cloud's plans (docs/specs/ada-cloud.md, section 7): the caps in plan_versions, a read counted against the org's
month (once per output), Free refused past it with what to do, every call held to the plan's rate, and the plan,
plans and usage of the API and the connector showing the cloud numbers."""

import asyncio
import types
import uuid

import httpx
import pytest
from redis.asyncio import Redis
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_ada import allowance, requests
from glyphh_ada.allowance import Allowance
from glyphh_ada.api.auth import AdaCaller
from glyphh_ada.api.call import send
from glyphh_ada.api.meter import admit
from glyphh_ada.process import Worker
from glyphh_server.errors import Unavailable
from glyphh_server.models import AdaUsage
from tests.ada.conftest import ADA, a_model, an_org, key_for, pinned, shape
from tests.ada.mcp import data, refused, signed_in, text, tool
from tests.conftest import REDIS_URL, UNREACHABLE_REDIS
from tests.db.helpers import person

API: str = "http://api.test"


def test_a_read_is_a_request_and_a_decide_one_per_output() -> None:
    assert requests.reads("decide", {"data": {}}) == 1
    assert requests.reads("decide", {"data": {}, "outputs": ["a", "b", "c"]}) == 3
    assert requests.reads("query", {}) == requests.reads("facts", {}) == 1
    assert requests.reads("record_many", {"cases": [1, 2]}) == requests.reads("job", {}) == 0
    assert requests.turns("2026-12") == "2027-01-01" and requests.turns("2026-10") == "2026-11-01"
    assert requests.before("2027-01") == "2026-12" and requests.before("2026-10") == "2026-09"


async def test_free_is_refused_past_its_month_saying_how_to_read_on(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who = await person(engine, "Free")
    key = await key_for(ada, who)
    await a_model(ada, key, n=12)
    first = await ada.post("/v1/decide", json={"model": "shapes", "data": shape(3)}, headers=key)
    assert first.status_code == 200, first.text
    month = requests.period()
    counted = Redis.from_url(REDIS_URL, decode_responses=True)
    assert await counted.get(requests.total_key(who.org_id, month)) == "1"
    await counted.set(requests.total_key(who.org_id, month), 10_000)
    over = await ada.post("/v1/models/shapes/query", json={"data": shape(3)}, headers=key)
    error = over.json()["error"]
    assert (over.status_code, error["code"], error["reason"]) == (403, "E_LIMIT", "requests")
    assert (error["used"], error["max"], error["plan"], error["upgrade"]) == (10_000, 10_000, "Free", "Basic")
    assert error["resets_at"] == requests.turns(month) and "Upgrade to Basic" in error["message"]
    assert await counted.get(requests.total_key(who.org_id, month)) == "10000"  # a refused read is not counted
    writes = await ada.post("/v1/models/shapes/record", json={"data": shape(90), "outcome": "good"}, headers=key)
    assert writes.status_code == 200  # writes are not requests
    await asyncio.sleep(1.2)  # Free's five calls a second
    auth = await signed_in(engine, who)
    said = await refused(ada, auth, "ada_decide", name="shapes", data=shape(3))
    assert (said["code"], said["reason"]) == ("E_LIMIT", "requests")
    used = (await ada.get("/v1/usage", headers=key)).json()
    assert used == {
        "plan": "Free",
        "month": month,
        "resets_at": requests.turns(month),
        "models": 1,
        "precedents": {"used": 13, "max": 5_000},
        "requests": {"used": 10_000, "max": 10_000, "over": 0, "overage": False},
        "requests_per_second": 5,
    }
    await counted.aclose()


async def test_a_plan_with_no_bigger_month_says_to_talk_to_us(
    engine: AsyncEngine, ada: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    who, key = await an_org(engine, ada)
    await pinned(engine, who.org_id, cloud_requests=1, cloud_overage=False)
    counted = Redis.from_url(REDIS_URL, decode_responses=True)
    await counted.set(requests.total_key(who.org_id, requests.period()), 99_000_000)

    async def no_plans(conn: object) -> list[object]:
        return []  # no self-serve plan reads more than this one

    monkeypatch.setattr(allowance, "newest_versions", no_plans)
    over = (await ada.post("/v1/models/shapes/query", json={"data": shape(3)}, headers=key)).json()["error"]
    assert over["upgrade"] is None and "sales@glyphh.ai" in over["message"]
    await counted.aclose()


async def test_every_call_is_held_to_the_plans_rate(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    await pinned(engine, who.org_id, cloud_rps=1)
    assert (await ada.get("/v1/models", headers=key)).status_code == 200
    again = await ada.get("/v1/models", headers=key)
    error = again.json()["error"]
    assert (again.status_code, error["code"], error["max"], again.headers["retry-after"]) == (429, "E_RATE", 1, "1")
    assert error["retry_after"] == 1 and "1 Ada calls a second" in error["message"]
    auth = await signed_in(engine, who)
    assert (await refused(ada, auth, "ada_models"))["code"] == "E_RATE"


async def test_the_months_count_starts_from_the_database(
    engine: AsyncEngine, ada: httpx.AsyncClient, worker: Worker
) -> None:
    who, key = await an_org(engine, ada)
    month = requests.period()
    async with engine.begin() as conn:
        await conn.execute(insert(AdaUsage).values(org_id=who.org_id, period=month, requests=7))
    first = (await ada.get("/v1/usage", headers=key)).json()
    assert first["requests"]["used"] == 7  # Redis has no count: the database's
    missing = await ada.post("/v1/models/nothing/query", json={"data": shape(3)}, headers=key)
    assert missing.status_code == 404  # a read is counted before it is asked
    used = (await ada.get("/v1/usage", headers=key)).json()
    assert (used["requests"]["used"], used["precedents"]["used"], used["models"], used["month"]) == (8, 0, 0, month)


async def test_redis_down_is_unavailable_never_a_hang(engine: AsyncEngine) -> None:
    state = types.SimpleNamespace(redis=Redis.from_url(UNREACHABLE_REDIS), engine=engine)
    who = AdaCaller(uuid.uuid4(), uuid.uuid4(), 1.0, allowance=Allowance("Team", None, None, 10, True))
    with pytest.raises(Unavailable):
        await admit(state, who, "query", {"data": {}})
    state.settings = ADA  # a caller nothing is counted for (an upload's link) meets Redis down at the queue
    with pytest.raises(Unavailable):
        await send(state, AdaCaller(uuid.uuid4(), uuid.uuid4(), 1.0), "m", "import_go", {"job": "j"})
    await state.redis.aclose()


async def test_plans_and_usage_show_the_cloud_numbers_with_ada_cloud_on(
    engine: AsyncEngine, ada: httpx.AsyncClient, client: httpx.AsyncClient, worker: Worker
) -> None:
    plans = {p["name"]: p["cloud"] for p in (await ada.get(f"{API}/v1/plans")).json()}
    assert plans["Free"] == {
        "precedents": 5_000,
        "requests_per_month": 10_000,
        "requests_per_second": 5,
        "overage": False,
        "overage_cents_per_10k": None,
    }
    assert plans["Basic"] == {
        "precedents": 10_000,
        "requests_per_month": 50_000,
        "requests_per_second": 10,
        "overage": True,
        "overage_cents_per_10k": 100,
    }
    assert (plans["Pro"]["precedents"], plans["Pro"]["requests_per_month"], plans["Pro"]["requests_per_second"]) == (
        100_000,
        1_000_000,
        50,
    )
    assert plans["Pro"]["overage"] and plans["Pro"]["overage_cents_per_10k"] == 100
    assert (plans["Team"]["precedents"], plans["Team"]["requests_per_month"]) == (1_000_000, 5_000_000)
    assert plans["Enterprise"]["requests_per_month"] is None
    assert all(p["cloud"] is None for p in (await client.get("/v1/plans")).json())  # off: none shown
    who, key = await an_org(engine, ada)
    await a_model(ada, key, n=5)
    await ada.post("/v1/decide", json={"model": "shapes", "data": shape(3)}, headers=key)
    billing = (await ada.get(f"{API}/v1/billing", headers=who.headers)).json()
    assert billing["cloud"]["requests"]["used"] == 1 and billing["cloud"]["precedents"] == {"used": 5, "max": 1_000_000}
    assert billing["plan"]["cloud"]["requests_per_month"] == 5_000_000
    me = (await ada.get(f"{API}/v1/me", headers=who.headers)).json()
    assert me["cloud"]["precedents"]["max"] == 1_000_000 and me["ada_cloud"] is True
    assert (await client.get("/v1/me", headers=who.headers)).json()["cloud"] is None
    auth = await signed_in(engine, who)
    plan = text(await tool(ada, auth, "plan"))
    assert "Ada Cloud 1,000,000 precedents, 5,000,000 reads a month (then $1 per 10,000 more), 200 calls" in plan
    listed = text(await tool(ada, auth, "plans")).splitlines()
    assert listed[0].endswith("Ada Cloud 5,000 precedents, 10,000 reads a month (then refused), 5 calls a second")
    assert listed[1].endswith(
        "Ada Cloud 10,000 precedents, 50,000 reads a month (then $1 per 10,000 more), 10 calls a second"
    )
    assert listed[4].endswith("Ada Cloud by contract")
    usage = await tool(ada, auth, "usage")
    lines = text(usage).splitlines()
    assert lines[0].startswith(f"Ada Cloud reads {requests.period()}: 1 of 5,000,000; the count starts again")
    assert lines[1] == "Ada Cloud precedents: 5 of 1,000,000, in 1 model."
    assert data(usage)["cloud"]["requests"]["used"] == 1


async def test_reads_past_a_metered_month_go_on_and_are_shown(engine: AsyncEngine, ada: httpx.AsyncClient) -> None:
    who, key = await an_org(engine, ada)
    await pinned(engine, who.org_id, cloud_requests=1, cloud_overage=True)
    counted = Redis.from_url(REDIS_URL, decode_responses=True)
    await counted.set(requests.total_key(who.org_id, requests.period()), 3)
    assert (await ada.get("/v1/usage", headers=key)).json()["requests"]["over"] == 2
    auth = await signed_in(engine, who)
    assert ", 2 past it, metered;" in text(await tool(ada, auth, "usage"))
    await counted.aclose()
