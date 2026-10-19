"""The receiver for rrotor's opt-in server-side logging: OTLP over HTTP (protobuf, gzipped or plain) with the runtime's
own token, answered 200 with OTLP's empty export response once kept; anything else is a refusal rrotor retries with
backoff. Never logged: the body, or the caller's address (obs/logs.py drops the access line for these paths)."""

from typing import Any

from fastapi import APIRouter, Request
from starlette.responses import Response

from glyphh_server.errors import Unauthorized
from glyphh_server.ops.link.presence import Refused, bearer, runtime_for
from glyphh_server.ops.otlp import body
from glyphh_server.ops.otlp.keep import keep

router = APIRouter(prefix="/v1/otlp/v1", tags=["telemetry"])

PROTOBUF: dict[str, Any] = {
    "requestBody": {
        "required": True,
        "content": {body.CONTENT_TYPE: {"schema": {"type": "string", "format": "binary"}}},
    },
    "responses": {"200": {"content": {body.CONTENT_TYPE: {"schema": {"type": "string", "format": "binary"}}}}},
}


async def _take(request: Request, signal: str) -> Response:
    """The token first (nothing is read for a caller without a good one), then the body within its limits, then the
    records kept."""
    engine = request.app.state.engine
    try:
        runtime = await runtime_for(engine, bearer(request.headers.get("authorization")))
    except Refused as err:
        raise Unauthorized(str(err)) from None
    sent = await body.read(request.stream(), request.headers)
    await keep(engine, runtime, signal, body.decoded(signal, sent, request.headers))
    return Response(body.answer(signal), media_type=body.CONTENT_TYPE)


@router.post("/logs", operation_id="otlpLogs", response_class=Response, openapi_extra=PROTOBUF)
async def logs(request: Request) -> Response:
    """A runtime's log records and audit events (`event_name` `rrotor.audit.<kind>`): ExportLogsServiceRequest."""
    return await _take(request, "logs")


@router.post("/metrics", operation_id="otlpMetrics", response_class=Response, openapi_extra=PROTOBUF)
async def metrics(request: Request) -> Response:
    """A runtime's metric points, one kept per series a minute: ExportMetricsServiceRequest."""
    return await _take(request, "metrics")


@router.post("/traces", operation_id="otlpTraces", response_class=Response, openapi_extra=PROTOBUF)
async def traces(request: Request) -> Response:
    """A runtime's spans: ExportTraceServiceRequest."""
    return await _take(request, "traces")
