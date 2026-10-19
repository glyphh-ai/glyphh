"""An OTLP request's body read within its limits and decoded: `application/x-protobuf` only (OTLP's JSON is not
taken: 415), gzipped or plain (any other encoding: 415), at most MAX_SENT bytes as sent and MAX_READ unzipped (413),
then parsed as the signal's export request (E_INVALID, 422, when it is not one)."""

import zlib
from collections.abc import AsyncIterator, Mapping
from typing import Any

from google.protobuf.message import DecodeError
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest, ExportLogsServiceResponse
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
    ExportMetricsServiceResponse,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)

from glyphh_server.errors import Invalid, TooLarge, UnsupportedMedia

CONTENT_TYPE: str = "application/x-protobuf"
MAX_SENT: int = 4 * 1024 * 1024  # rrotor sends batches of 512 records, gzipped: far below
MAX_READ: int = 16 * 1024 * 1024  # unzipped: a small body cannot open into a large one
SIGNALS: dict[str, tuple[type[Any], type[Any]]] = {
    "logs": (ExportLogsServiceRequest, ExportLogsServiceResponse),
    "metrics": (ExportMetricsServiceRequest, ExportMetricsServiceResponse),
    "traces": (ExportTraceServiceRequest, ExportTraceServiceResponse),
}


def _encoding(headers: Mapping[str, str]) -> str:
    """The body's encoding, after its type is checked."""
    kind = headers.get("content-type", "").partition(";")[0].strip().lower()
    if kind != CONTENT_TYPE:
        raise UnsupportedMedia(f"Send OTLP as protobuf: Content-Type: {CONTENT_TYPE}.", reason="content_type")
    encoding = headers.get("content-encoding", "identity").strip().lower() or "identity"
    if encoding not in ("gzip", "identity"):
        raise UnsupportedMedia("Send the body gzipped or plain.", reason="content_encoding")
    return encoding


def _too_large(limit: int) -> TooLarge:
    return TooLarge(f"The body is over {limit} bytes: send smaller batches.", limit=limit)


async def read(stream: AsyncIterator[bytes], headers: Mapping[str, str]) -> bytes:
    """The body as sent, refused past MAX_SENT before it is all read."""
    _encoding(headers)
    said = headers.get("content-length", "")
    if said.isdigit() and int(said) > MAX_SENT:
        raise _too_large(MAX_SENT)
    body = bytearray()
    async for chunk in stream:
        body += chunk
        if len(body) > MAX_SENT:
            raise _too_large(MAX_SENT)
    return bytes(body)


def _unzipped(body: bytes) -> bytes:
    opened = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        out = opened.decompress(body, MAX_READ + 1)
    except zlib.error:
        raise Invalid("The body is not gzip.", reason="gzip") from None
    if len(out) > MAX_READ:
        raise _too_large(MAX_READ)
    if not opened.eof:
        raise Invalid("The gzip body ends early.", reason="gzip")
    return out


def decoded(signal: str, body: bytes, headers: Mapping[str, str]) -> Any:
    """The signal's export request."""
    raw = _unzipped(body) if _encoding(headers) == "gzip" else body
    message = SIGNALS[signal][0]()
    try:
        message.ParseFromString(raw)
    except DecodeError:
        raise Invalid(f"The body is not an OTLP {signal} export request.", reason="protobuf") from None
    return message


def answer(signal: str) -> bytes:
    """OTLP's success: the signal's export response, empty (everything taken)."""
    return bytes(SIGNALS[signal][1]().SerializeToString())
