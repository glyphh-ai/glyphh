"""What the platform reads of server-side logging: the org's log records (filtered and paged), its audit events, its
metrics' latest values; only the caller's own org's; the connector's `logs` tool; and retention, purged by the tick."""

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import TelemetryLog, TelemetryMetric, TelemetrySpan
from glyphh_server.ops.telemetry.retention import purge
from tests.api.test_self_hosted import made, rt
from tests.connector import granted, tool
from tests.db.helpers import Person, person
from tests.link import Rt
from tests.otlp import audit, counter, gauge, log, logs, metrics, now_ns, resource, send, span, traces


async def a_runtime(client: httpx.AsyncClient, who: Person, name: str = "Acme") -> Rt:
    return rt(await made(client, who, f"https://{name.lower()}.example.test", name))


async def sent(client: httpx.AsyncClient, runtime: Rt, node: str, *records: Any) -> None:
    res = await send(client, "logs", logs(resource(runtime.id, node), *records), runtime.token)
    assert res.status_code == 200, res.text


async def get(client: httpx.AsyncClient, who: Person, path: str, **params: Any) -> dict[str, Any]:
    res = await client.get(f"/v1/telemetry/{path}", params=params, headers=who.headers)
    assert res.status_code == 200, res.text
    return res.json()


async def test_logs_newest_first_filtered_and_paged(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    one, two = await a_runtime(client, ada, "One"), await a_runtime(client, ada, "Two")
    await sent(client, one, "n-0", log("started 100%_done", 9, at=now_ns(30)), log("slow call", 13, at=now_ns(20)))
    await sent(client, one, "n-1", log("crashed", 17, at=now_ns(10)), audit("run.call"))
    await sent(client, two, "n-0", log("other runtime", 5, at=now_ns(5)))
    page = await get(client, ada, "logs")
    assert [r["body"] for r in page["records"]] == ["other runtime", "crashed", "slow call", "started 100%_done"]
    assert page["next_cursor"] is None
    first = page["records"][0]
    assert set(first) == {
        "id",
        "at",
        "runtime_id",
        "runtime",
        "node_id",
        "level",
        "severity",
        "body",
        "trace_id",
        "span_id",
        "attributes",
    }
    assert (first["runtime"], first["runtime_id"], first["node_id"], first["level"]) == (
        "Two",
        str(two.id),
        "n-0",
        "debug",
    )
    assert [r["body"] for r in (await get(client, ada, "logs", runtime=str(one.id), node="n-0"))["records"]] == [
        "slow call",
        "started 100%_done",
    ]
    assert [r["body"] for r in (await get(client, ada, "logs", level="warn"))["records"]] == ["crashed", "slow call"]
    assert [r["body"] for r in (await get(client, ada, "logs", text="100%_"))["records"]] == ["started 100%_done"]
    assert [r["body"] for r in (await get(client, ada, "logs", text="0%x"))["records"]] == []
    since = (datetime.now(UTC) - timedelta(seconds=15)).isoformat()
    assert [r["body"] for r in (await get(client, ada, "logs", since=since))["records"]] == ["other runtime", "crashed"]
    seen, cursor = [], None
    while True:
        page = await get(client, ada, "logs", limit=3, **({"cursor": cursor} if cursor else {}))
        seen += [r["body"] for r in page["records"]]
        if not (cursor := page["next_cursor"]):
            break
    assert seen == ["other runtime", "crashed", "slow call", "started 100%_done"]


@pytest.mark.parametrize("cursor", ["!!!", "bm90LWEtY3Vyc29y", "MjAyNi0xMC0xOVQwOTowMDowMHxub3QtYS11dWlk"])
async def test_a_cursor_not_given_by_a_page_is_refused(
    client: httpx.AsyncClient, engine: AsyncEngine, cursor: str
) -> None:
    ada = await person(engine)
    res = await client.get("/v1/telemetry/audit", params={"cursor": cursor}, headers=ada.headers)
    assert res.status_code == 422 and res.json()["error"]["reason"] == "cursor"


async def test_audit_events_with_their_kind(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Team")
    runtime = await a_runtime(client, ada)
    deny = audit("access.denied", at=now_ns(5), **{"outcome.code": "E_UNAUTHORIZED", "actor.type": "key"})
    await sent(client, runtime, "head", audit("run.call", at=now_ns(10), model="incidents"), deny, log("not audit"))
    events = (await get(client, ada, "audit"))["events"]
    assert [e["kind"] for e in events] == ["access.denied", "run.call"]
    assert set(events[0]) == {"id", "at", "runtime_id", "runtime", "node_id", "kind", "attributes"}
    assert events[0]["attributes"] == {"kind": "access.denied", "outcome.code": "E_UNAUTHORIZED", "actor.type": "key"}
    assert (events[1]["node_id"], events[1]["runtime"]) == ("head", "Acme")
    assert [e["kind"] for e in (await get(client, ada, "audit", kind="run.call"))["events"]] == ["run.call"]
    paged = await get(client, ada, "audit", limit=1)
    assert len(paged["events"]) == 1 and paged["next_cursor"]
    after = await get(client, ada, "audit", limit=1, cursor=paged["next_cursor"])
    assert [e["kind"] for e in after["events"]] == ["run.call"] and after["next_cursor"] is None


async def test_metrics_latest_per_series(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    runtime = await a_runtime(client, ada)
    early, late = now_ns(180), now_ns(5)
    for at, runs in ((early, 2), (late, 7)):
        found = metrics(resource(runtime.id, "n-0"), counter("rrotor.runs", runs, at, model="m", status="done"))
        assert (await send(client, "metrics", found, runtime.token)).status_code == 200
    found = metrics(resource(runtime.id, "n-1"), gauge("rrotor.precedents", 1200, late, unit="{precedent}", model="m"))
    assert (await send(client, "metrics", found, runtime.token)).status_code == 200
    latest = (await get(client, ada, "metrics"))["metrics"]
    assert [(m["node_id"], m["name"], m["value"]) for m in latest] == [
        ("n-0", "rrotor.runs", 7.0),
        ("n-1", "rrotor.precedents", 1200.0),
    ]
    runs = latest[0]
    assert set(runs) == {
        "runtime_id",
        "runtime",
        "node_id",
        "name",
        "unit",
        "kind",
        "value",
        "count",
        "attributes",
        "at",
    }
    assert (runs["kind"], runs["unit"], runs["count"], runs["attributes"]) == (
        "sum",
        "{run}",
        None,
        {"model": "m", "status": "done"},
    )
    assert [m["name"] for m in (await get(client, ada, "metrics", node="n-1"))["metrics"]] == ["rrotor.precedents"]
    assert (await get(client, ada, "metrics", name="nope", runtime=str(runtime.id)))["metrics"] == []
    async with engine.connect() as conn:
        assert (
            await conn.execute(
                select(func.count()).select_from(TelemetryMetric).where(TelemetryMetric.rrotor_id == runtime.id)
            )
        ).scalar_one() == 3


async def test_only_the_callers_org_is_seen(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada, eve = await person(engine), await person(engine)
    runtime = await a_runtime(client, ada)
    await sent(client, runtime, "n-0", log("ada's"), audit("run.call"))
    found = metrics(resource(runtime.id), gauge("g", 1.0))
    assert (await send(client, "metrics", found, runtime.token)).status_code == 200
    assert (await get(client, eve, "logs"))["records"] == [] and (await get(client, eve, "audit"))["events"] == []
    assert (await get(client, eve, "metrics"))["metrics"] == []
    assert (await get(client, eve, "logs", runtime=str(runtime.id)))["records"] == []
    assert (await client.get("/v1/telemetry/logs")).status_code == 401


async def test_the_connectors_logs_tool(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine, "Pro")
    _, auth = await granted(engine, ada)
    empty = await tool(client, auth, "logs")
    assert "RROTOR_SERVER_LOGS=on" in empty["content"][0]["text"] and "kept 7 days" in empty["content"][0]["text"]
    runtime = await a_runtime(client, ada)
    await sent(client, runtime, "n-0", log("it broke", 17), audit("model.deploy"))
    shown = await tool(client, auth, "logs", level="error")
    assert "Acme/n-0 error: it broke" in shown["content"][0]["text"] and not shown["isError"]
    assert shown["structuredContent"]["records"][0]["body"] == "it broke"
    events = await tool(client, auth, "logs", audit=True, runtime_id=str(runtime.id))
    assert "Acme/n-0 model.deploy" in events["content"][0]["text"]
    assert events["structuredContent"]["events"][0]["kind"] == "model.deploy"


async def test_retention_purges_what_is_older(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    runtime = await a_runtime(client, await person(engine))
    await sent(client, runtime, "n-0", log("old", at=now_ns(8 * 86400)), log("new"))
    assert (
        await send(client, "metrics", metrics(resource(runtime.id), gauge("g", 1.0, now_ns(9 * 86400))), runtime.token)
    ).status_code == 200
    assert (
        await send(client, "traces", traces(resource(runtime.id), span(start=now_ns(8 * 86400))), runtime.token)
    ).status_code == 200
    assert await purge(engine, 7) >= 3
    async with engine.connect() as conn:
        bodies = (await conn.execute(select(TelemetryLog.body).where(TelemetryLog.rrotor_id == runtime.id))).scalars()
        assert list(bodies) == ["new"]
        for table in (TelemetryMetric, TelemetrySpan):
            left = select(func.count()).select_from(table).where(table.rrotor_id == runtime.id)
            assert (await conn.execute(left)).scalar_one() == 0


async def test_a_deleted_runtime_takes_its_telemetry(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    runtime = await a_runtime(client, ada)
    await sent(client, runtime, "n-0", log("gone with it"))
    assert (await client.delete(f"/v1/runtimes/self/{runtime.id}", headers=ada.headers)).status_code == 204
    async with engine.connect() as conn:
        assert (await conn.execute(select(TelemetryLog).where(TelemetryLog.rrotor_id == runtime.id))).first() is None
