import json
import logging
from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from glyphh_server.app import create_app
from glyphh_server.errors import Conflict, Unavailable
from tests.conftest import SETTINGS, _client


def _probe_app() -> FastAPI:
    app = create_app(SETTINGS)

    async def refuse() -> None:
        raise Conflict("That name is taken.", field="name")

    async def unavailable() -> None:
        raise Unavailable("Pipedream is down.")

    async def crash() -> None:
        raise RuntimeError("secret internals")

    async def count(n: int) -> dict[str, int]:
        return {"n": n}

    async def crash_midway() -> StreamingResponse:
        async def body() -> AsyncIterator[bytes]:
            yield b"partial"
            raise RuntimeError("cut off")

        return StreamingResponse(body())

    for path, fn in (("/probe/refuse", refuse), ("/probe/unavailable", unavailable), ("/probe/crash", crash),
                     ("/probe/count", count), ("/probe/stream", crash_midway)):
        app.add_api_route(path, fn, methods=["GET"])
    return app


@pytest.fixture
async def probe(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    async for c in _client(_probe_app()):
        yield c


async def test_a_refusal_has_its_code_message_detail_and_trace_id(probe: httpx.AsyncClient) -> None:
    res = await probe.get("/probe/refuse")
    assert res.status_code == 409
    err = res.json()["error"]
    assert (err["code"], err["message"], err["field"]) == ("E_CONFLICT", "That name is taken.", "name")
    assert err["trace_id"] == res.headers["x-request-id"]


async def test_a_server_side_refusal_keeps_its_own_code(probe: httpx.AsyncClient) -> None:
    res = await probe.get("/probe/unavailable")
    assert res.status_code == 503 and res.json()["error"]["code"] == "E_UNAVAILABLE"


async def test_a_crash_fails_closed_without_its_message_and_is_logged_with_its_trace(
    probe: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        res = await probe.get("/probe/crash", headers={"x-request-id": "client-trace-0001"})
    assert res.status_code == 500
    err = res.json()["error"]
    assert err["code"] == "E_INTERNAL" and "secret internals" not in res.text
    assert err["trace_id"] == res.headers["x-request-id"] == "client-trace-0001"
    crashed = [r for r in caplog.records if r.getMessage() == "crashed"]
    assert crashed and crashed[0].exc_info and "secret internals" in str(crashed[0].exc_info[1])


async def test_a_crash_after_the_response_started_is_logged_and_cuts_the_body(
    probe: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        res = await probe.get("/probe/stream")
    assert res.status_code == 200 and res.text == "partial"
    assert any(r.getMessage() == "crashed" for r in caplog.records)


async def test_invalid_input_lists_its_problems(probe: httpx.AsyncClient) -> None:
    res = await probe.get("/probe/count", params={"n": "many"})
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "E_INVALID" and err["problems"][0]["loc"] == ["query", "n"]


async def test_an_unknown_path_and_a_wrong_method_answer_in_the_same_shape(probe: httpx.AsyncClient) -> None:
    missing = await probe.get("/nowhere")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "E_NOT_FOUND"
    wrong = await probe.delete("/v1/health")
    assert wrong.status_code == 405 and wrong.json()["error"]["code"] == "E_METHOD_NOT_ALLOWED"


async def test_an_unmapped_http_status_has_a_generic_code(probe: httpx.AsyncClient) -> None:
    from starlette.exceptions import HTTPException

    app = probe._transport.app  # type: ignore[attr-defined]

    async def teapot() -> None:
        raise HTTPException(status_code=418, detail="I'm a teapot")

    app.add_api_route("/probe/teapot", teapot, methods=["GET"])
    res = await probe.get("/probe/teapot")
    assert res.status_code == 418 and res.json()["error"] == {
        "code": "E_HTTP", "message": "I'm a teapot", "trace_id": res.headers["x-request-id"]}


async def test_every_request_is_logged_once_with_its_status_and_time(
    probe: httpx.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="glyphh.request"):
        await probe.get("/v1/health")
    lines = [r for r in caplog.records if r.getMessage() == "request"]
    assert len(lines) == 1
    assert lines[0].fields["status"] == 200 and lines[0].fields["path"] == "/v1/health"  # type: ignore[attr-defined]
    assert json.dumps(lines[0].fields)  # type: ignore[attr-defined]


async def test_a_bad_trace_id_from_a_caller_is_replaced(probe: httpx.AsyncClient) -> None:
    res = await probe.get("/v1/health", headers={"x-request-id": "bad id!"})
    assert res.headers["x-request-id"] != "bad id!" and len(res.headers["x-request-id"]) == 32
