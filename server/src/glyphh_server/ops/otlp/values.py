"""OTLP's values as plain ones: attributes as a dict (what must never be kept dropped), times as instants, ids as hex,
and a request's resource read for its runtime and node.

rrotor strips client addresses and payloads before it sends (its otel.py, NEVER_TO_GLYPHH); NEVER drops them again
here, at every depth, so no row ever holds them whatever a sender does. Postgres keeps no NUL in text, and JSON no NaN:
both are made safe."""

import base64
import math
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from glyphh_server.errors import Forbidden

NEVER: frozenset[str] = frozenset(
    {"client", "inputs", "data", "rrotor.inputs", "rrotor.data", "http.client_ip", "network.peer.address"}
)
NEVER_PREFIXES: tuple[str, ...] = ("client.", "network.peer.")
AHEAD: timedelta = timedelta(minutes=5)  # a clock this far ahead is read as now
NODE_MAX: int = 253


def kept(key: str) -> bool:
    return key not in NEVER and not key.startswith(NEVER_PREFIXES)


def safe(text: str) -> str:
    return text.replace("\x00", "")


def plain(value: Any) -> Any:
    """An AnyValue's plain value: a string, a number, a bool, a list, a dict, bytes as base64, or None."""
    which = value.WhichOneof("value")
    if which is None:
        return None
    if which == "array_value":
        return [plain(v) for v in value.array_value.values]
    if which == "kvlist_value":
        return attributes(value.kvlist_value.values)
    if which == "bytes_value":
        return base64.b64encode(value.bytes_value).decode()
    found = getattr(value, which)
    if isinstance(found, str):
        return safe(found)
    if isinstance(found, float) and not math.isfinite(found):
        return str(found)
    return found


def attributes(pairs: Any) -> dict[str, Any]:
    return {safe(kv.key): plain(kv.value) for kv in pairs if kept(kv.key)}


def moment(nanos: int, now: datetime) -> datetime | None:
    """A Unix time in nanoseconds as an instant; none for 0 (unset), now for a clock ahead of ours."""
    if nanos <= 0:
        return None
    at = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=nanos // 1000)
    return now if at > now + AHEAD else at


def hex_id(raw: bytes) -> str | None:
    return raw.hex() if raw.strip(b"\x00") else None


def number(value: float) -> float | None:
    return value if math.isfinite(value) else None


def node_of(resource: Any, runtime_id: uuid.UUID) -> str | None:
    """The node a resource names (`service.instance.id`), once its `rrotor.runtime.id`, when it says one, is the
    token's runtime: a batch naming another runtime is refused whole."""
    said = attributes(resource.attributes)
    claimed = said.get("rrotor.runtime.id")
    if claimed is not None and str(claimed) != str(runtime_id):
        raise Forbidden(
            "This batch names another runtime (rrotor.runtime.id): send it with that runtime's token.",
            reason="runtime_mismatch",
        )
    node = said.get("service.instance.id")
    return str(node)[:NODE_MAX] if node not in (None, "") else None
