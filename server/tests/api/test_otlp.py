"""The receiver for rrotor's server-side logging: OTLP protobuf, gzipped, with the runtime token; each signal kept in
the runtime's org with its node; audit events marked; what must never be kept dropped; anything else refused with a
status rrotor retries."""

import gzip
import uuid
from typing import Any

import httpx
import pytest
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.models import TelemetryLog, TelemetryMetric, TelemetrySpan
from glyphh_server.ops.otlp import body
from tests.api.test_self_hosted import made, rt
from tests.db.helpers import person
from tests.link import hosted_runtime, local_runtime
from tests.otlp import (
    SECOND,
    audit,
    counter,
    gauge,
    histogram,
    log,
    logs,
    metrics,
    now_ns,
    resource,
    send,
    span,
    traces,
)


async def rows(engine: AsyncEngine, table: Any, runtime_id: uuid.UUID) -> list[Any]:
    async with engine.connect() as conn:
        return list(await conn.execute(select(table).where(table.rrotor_id == runtime_id)))


async def test_log_records_and_audit_events_are_kept_with_their_node_and_org(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    ada = await person(engine, "Pro")
    runtime = rt(await made(client, ada))
    line = log(
        "run ended", 17, "ERROR", attrs={"logger": "rrotor.runs", "run_id": "r-1"}, trace=b"\x0a" * 16, span=b"\x0b" * 8
    )
    event = audit("run.call", **{"actor.type": "key", "actor.key_sha256": "3f2a", "outcome.status": "done"})
    res = await send(client, "logs", logs(resource(runtime.id, "rrotor-1"), line, event), runtime.token)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/x-protobuf"
    ExportLogsServiceResponse().ParseFromString(res.content)
    kept = sorted(await rows(engine, TelemetryLog, runtime.id), key=lambda r: r.severity)
    assert [(r.org_id, r.node_id) for r in kept] == [(ada.org_id, "rrotor-1")] * 2
    first, second = kept
    assert (first.audit, first.body, first.level, first.attributes["actor.type"]) == (
        "run.call",
        "run.call",
        "info",
        "key",
    )
    assert (second.audit, second.level, second.severity, second.body) == (None, "error", 17, "run ended")
    assert (second.trace_id, second.span_id) == ("0a" * 16, "0b" * 8)
    assert second.attributes == {"logger": "rrotor.runs", "run_id": "r-1"}


async def test_client_addresses_and_payloads_are_never_kept_at_any_depth(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    runtime = rt(await made(client, await person(engine)))
    attrs = {
        "client": "10.0.4.17",
        "client.address": "10.0.4.17",
        "network.peer.address": "10.0.4.17",
        "inputs": "secret",
        "data": "answer",
        "rrotor.inputs": "x",
        "model": "incidents",
        "nested": {"client": "10.0.4.17", "keep": [1, 2.5, True, None, b"\x00\x01"]},
    }
    res = await send(client, "logs", logs(resource(runtime.id), log("hi\x00there", attrs=attrs)), runtime.token)
    assert res.status_code == 200, res.text
    (kept,) = await rows(engine, TelemetryLog, runtime.id)
    assert kept.attributes == {"model": "incidents", "nested": {"keep": [1, 2.5, True, None, "AAE="]}}
    assert kept.body == "hithere"


async def test_metrics_keep_one_point_per_series_a_minute_the_newest(
    client: httpx.AsyncClient, engine: AsyncEngine
) -> None:
    runtime = rt(await made(client, await person(engine)))
    res_ = resource(runtime.id)
    minute = (now_ns() // (60 * SECOND)) * 60 * SECOND
    early, late = minute + SECOND, minute + 30 * SECOND
    first = metrics(
        res_,
        counter("rrotor.runs", 3, late, model="m", status="done"),
        counter("rrotor.runs", 2, early, model="m", status="done"),
        gauge("rrotor.precedents", 1200, early, model="m"),
        histogram("rrotor.run.seconds", 4.5, 9, early, model="m"),
    )
    assert (await send(client, "metrics", first, runtime.token)).status_code == 200
    older = metrics(
        res_,
        counter("rrotor.runs", 1, early, model="m", status="done"),
        gauge("rrotor.precedents", 0.5, late, model="m"),
    )
    assert (await send(client, "metrics", older, runtime.token, zipped=False)).status_code == 200
    kept = {r.name: r for r in await rows(engine, TelemetryMetric, runtime.id)}
    assert (kept["rrotor.runs"].value, kept["rrotor.runs"].kind, kept["rrotor.runs"].count) == (3.0, "sum", None)
    assert (kept["rrotor.precedents"].value, kept["rrotor.precedents"].kind) == (0.5, "gauge")
    assert (kept["rrotor.run.seconds"].value, kept["rrotor.run.seconds"].count) == (4.5, 9)
    assert kept["rrotor.run.seconds"].kind == "histogram" and len(kept) == 3


async def test_spans_are_kept(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    runtime = await hosted_runtime(engine, await person(engine, "Pro"))
    child = span("sandbox.start", 1, 2, span=b"\x03" * 8, parent=b"\x02" * 8, attrs={"client": "x", "model": "m"})
    res = await send(client, "traces", traces(resource(runtime.id, None), span(), child), runtime.token)
    assert res.status_code == 200, res.text
    kept = {r.name: r for r in await rows(engine, TelemetrySpan, runtime.id)}
    top, inner = kept["POST /v1/run"], kept["sandbox.start"]
    assert (top.kind, top.status, top.parent_span_id, top.node_id) == ("server", "ok", None, None)
    assert (inner.kind, inner.status, inner.parent_span_id, inner.attributes) == (
        "internal",
        "error",
        "02" * 8,
        {"model": "m"},
    )
    assert (top.ended_at - top.started_at).total_seconds() == 0.25 and top.trace_id == "01" * 16


async def test_a_batch_naming_another_runtime_is_refused_whole(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    runtime = rt(await made(client, await person(engine)))
    batch = logs(resource(runtime.id), log())
    batch.resource_logs.append(logs(resource(uuid.uuid4()), log()).resource_logs[0])
    res = await send(client, "logs", batch, runtime.token)
    assert res.status_code == 403 and res.json()["error"]["reason"] == "runtime_mismatch"
    assert await rows(engine, TelemetryLog, runtime.id) == []
    unnamed = logs(resource(None), log("from a runtime that says none"))
    assert (await send(client, "logs", unnamed, runtime.token)).status_code == 200


async def test_an_empty_request_is_taken(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    runtime = await local_runtime(engine, await person(engine))
    assert (await send(client, "traces", traces(resource(runtime.id)), runtime.token)).status_code == 200
    assert (await send(client, "logs", b"", runtime.token, zipped=False)).status_code == 200


@pytest.mark.parametrize("token", [None, "not-a-runtime-token"])
async def test_a_runtime_token_is_required(client: httpx.AsyncClient, engine: AsyncEngine, token: str | None) -> None:
    res = await send(client, "logs", logs(resource(None), log()), token)
    assert res.status_code == 401 and res.json()["error"]["code"] == "E_UNAUTHORIZED"


async def test_a_persons_token_is_not_a_runtime_token(client: httpx.AsyncClient, engine: AsyncEngine) -> None:
    ada = await person(engine)
    token = ada.headers["authorization"].removeprefix("Bearer ")
    assert (await send(client, "logs", logs(resource(None), log()), token)).status_code == 401


@pytest.mark.parametrize(
    ("headers", "reason"),
    [
        ({"content-type": "application/json"}, "content_type"),
        ({"content-type": "text/plain"}, "content_type"),
        ({"content-encoding": "br"}, "content_encoding"),
    ],
)
async def test_other_content_is_refused_415(
    client: httpx.AsyncClient, engine: AsyncEngine, headers: dict[str, str], reason: str
) -> None:
    runtime = rt(await made(client, await person(engine)))
    res = await send(client, "logs", logs(resource(runtime.id), log()), runtime.token, **headers)
    assert res.status_code == 415 and res.json()["error"] == res.json()["error"] | {
        "code": "E_UNSUPPORTED_MEDIA",
        "reason": reason,
    }


async def test_a_body_too_large_is_refused_413(
    client: httpx.AsyncClient, engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = rt(await made(client, await person(engine)))
    big = logs(resource(runtime.id), *[log("x" * 1000) for _ in range(40)])
    monkeypatch.setattr(body, "MAX_SENT", 2_000)
    res = await send(client, "logs", big, runtime.token, zipped=False)
    assert res.status_code == 413 and res.json()["error"]["code"] == "E_TOO_LARGE"

    async def streamed() -> Any:
        for _ in range(3):
            yield b"\x00" * 1_000

    sent = {"authorization": f"Bearer {runtime.token}", "content-type": "application/x-protobuf"}
    assert (await client.post("/v1/otlp/v1/logs", content=streamed(), headers=sent)).status_code == 413
    monkeypatch.setattr(body, "MAX_SENT", 4_000_000)
    monkeypatch.setattr(body, "MAX_READ", 10_000)
    opened = await send(client, "logs", big, runtime.token)
    assert opened.status_code == 413 and opened.json()["error"]["limit"] == 10_000


@pytest.mark.parametrize(
    ("raw", "encoding", "reason"),
    [
        (b"not gzip at all", "gzip", "gzip"),
        (gzip.compress(b"\x0a\x05hello")[:-12], "gzip", "gzip"),
        (b"\xff\xff\xff", "identity", "protobuf"),
    ],
)
async def test_a_body_that_is_not_otlp_is_refused(
    client: httpx.AsyncClient, engine: AsyncEngine, raw: bytes, encoding: str, reason: str
) -> None:
    runtime = rt(await made(client, await person(engine)))
    res = await send(client, "metrics", raw, runtime.token, zipped=False, **{"content-encoding": encoding})
    assert res.status_code == 422 and res.json()["error"]["reason"] == reason


async def test_the_routes_are_in_the_spec_as_protobuf(client: httpx.AsyncClient) -> None:
    spec = (await client.get("/openapi.json")).json()
    for signal in ("logs", "metrics", "traces"):
        posted = spec["paths"][f"/v1/otlp/v1/{signal}"]["post"]
        assert "application/x-protobuf" in posted["requestBody"]["content"]


def test_the_answer_is_the_empty_export_response() -> None:
    assert all(body.answer(s) == b"" for s in body.SIGNALS)
