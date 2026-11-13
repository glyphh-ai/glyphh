"""One MCP request, read and checked. MCP 2026-07-28 carries its version and the client's capabilities in each
request's _meta, mirrored in headers the server checks against the body; the earlier revisions (2025-11-25 back to
2025-03-26) open with initialize and carry no capabilities per request. Both are served, statelessly."""

import base64
import binascii
import json
from dataclasses import dataclass, field
from typing import Any

from starlette.datastructures import Headers

MODERN: str = "2026-07-28"
LEGACY: tuple[str, ...] = ("2025-11-25", "2025-06-18", "2025-03-26")
SUPPORTED: tuple[str, ...] = (MODERN, *LEGACY)
VERSION: str = "io.modelcontextprotocol/protocolVersion"
CAPABILITIES: str = "io.modelcontextprotocol/clientCapabilities"
NAMED: dict[str, str] = {"tools/call": "name", "resources/read": "uri"}
# MCP 2026-07-28 caching: these results must carry ttlMs and cacheScope (a client's SDK refuses one without them, as
# claude.ai's did the decision card's resources/read). Never reused: what they hold depends on who asks and changes.
CACHEABLE: frozenset[str] = frozenset(
    {"tools/list", "resources/list", "resources/templates/list", "prompts/list", "resources/read"}
)
NO_CACHE: dict[str, Any] = {"ttlMs": 0, "cacheScope": "private"}

PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS = -32700, -32600, -32601, -32602
HEADER_MISMATCH, UNSUPPORTED_VERSION = -32020, -32022


class RpcError(Exception):
    def __init__(self, code: int, message: str, status: int = 200, data: Any = None) -> None:
        super().__init__(message)
        self.code, self.message, self.status, self.data = code, message, status, data
        self.id: str | int | None = None


@dataclass(frozen=True, slots=True)
class Call:
    """A request (id set) or a notification (id None), and which revision it speaks."""

    id: str | int | None
    method: str
    params: dict[str, Any]
    version: str
    capabilities: dict[str, Any] | None = field(default=None)

    @property
    def modern(self) -> bool:
        return self.version == MODERN


def _message(body: bytes) -> dict[str, Any]:
    try:
        msg = json.loads(body)
    except ValueError as err:
        raise RpcError(PARSE_ERROR, "The body is not JSON.", 400) from err
    ok = isinstance(msg, dict) and msg.get("jsonrpc") == "2.0" and isinstance(msg.get("method"), str)
    if not ok or not isinstance(msg.get("params", {}), dict):
        raise RpcError(INVALID_REQUEST, "One JSON-RPC 2.0 request or notification per POST.", 400)
    if "id" in msg and (isinstance(msg["id"], bool) or not isinstance(msg["id"], str | int)):
        raise RpcError(INVALID_REQUEST, "A request's id is a string or an integer.", 400)
    return msg


def header_value(raw: str | None) -> str | None:
    """A mirrored header's value, its Base64 sentinel form (=?base64?…?=) decoded."""
    if raw is None or not (raw.startswith("=?base64?") and raw.endswith("?=")):
        return raw
    try:
        return base64.b64decode(raw[9:-2], validate=True).decode()
    except (binascii.Error, UnicodeDecodeError) as err:
        raise RpcError(HEADER_MISMATCH, "A header's Base64 value is malformed.", 400) from err


def _check_headers(headers: Headers, method: str, params: dict[str, Any]) -> None:
    if header_value(headers.get("mcp-method")) != method:
        raise RpcError(HEADER_MISMATCH, f"The Mcp-Method header doesn't match the body's method {method}.", 400)
    named = NAMED.get(method)
    if named and header_value(headers.get("mcp-name")) != params.get(named):
        raise RpcError(HEADER_MISMATCH, f"The Mcp-Name header doesn't match the body's {named}.", 400)


def _modern(msg: dict[str, Any], headers: Headers) -> Call:
    params = msg.get("params", {})
    meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
    version, caps = meta.get(VERSION), meta.get(CAPABILITIES)
    if version is None or not isinstance(caps, dict):
        raise RpcError(INVALID_PARAMS, f"Each request's _meta needs {VERSION} and {CAPABILITIES}.", 400)
    if version != MODERN:
        raise unsupported(version)
    if headers.get("mcp-protocol-version") != version:
        raise RpcError(HEADER_MISMATCH, "The MCP-Protocol-Version header doesn't match the body's _meta.", 400)
    _check_headers(headers, msg["method"], params)
    return Call(msg.get("id"), msg["method"], params, version, caps)


def read(body: bytes, headers: Headers) -> Call:
    msg = _message(body)
    try:
        return _era(msg, headers)
    except RpcError as err:
        err.id = msg.get("id")
        raise


def _era(msg: dict[str, Any], headers: Headers) -> Call:
    asked = headers.get("mcp-protocol-version")
    meta = msg.get("params", {}).get("_meta")
    if asked == MODERN or (isinstance(meta, dict) and VERSION in meta):
        return _modern(msg, headers)
    if asked is not None and asked not in LEGACY:
        raise unsupported(asked)
    return Call(msg.get("id"), msg["method"], msg.get("params", {}), asked or LEGACY[-1])


def unsupported(version: object) -> RpcError:
    data = {"supported": list(SUPPORTED), "requested": version}
    return RpcError(UNSUPPORTED_VERSION, "Unsupported protocol version", 400, data)


def answer(call: Call, result: dict[str, Any], server_info: dict[str, str]) -> dict[str, Any]:
    if call.modern:
        result = {**result, "resultType": "complete", "_meta": {"io.modelcontextprotocol/serverInfo": server_info}}
        if call.method in CACHEABLE:
            result = {**NO_CACHE, **result}
    return {"jsonrpc": "2.0", "id": call.id, "result": result}


def failure(err: RpcError) -> dict[str, Any]:
    error: dict[str, Any] = {"code": err.code, "message": err.message}
    if err.data is not None:
        error["data"] = err.data
    body: dict[str, Any] = {"jsonrpc": "2.0", "error": error}
    if err.id is not None:
        body["id"] = err.id
    return body
