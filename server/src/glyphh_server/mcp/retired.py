"""The connector, wound down (GLYPHH_PRODUCTS off): `/mcp` still speaks MCP, so a client that connects is told the
truth instead of hanging or looping through a sign-in that leads nowhere. No token is asked for (there is nothing of
anyone's to show): the handshake answers with the retirement as its instructions, every list is empty, and a tool
call or a resource read is a JSON-RPC error carrying the API's code, E_WOUND_DOWN."""

from typing import Any

from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
from starlette.responses import Response

from glyphh_server.api.wound_down import RETIRED
from glyphh_server.errors import WoundDown
from glyphh_server.mcp import protocol
from glyphh_server.mcp.protocol import LEGACY, MODERN, Call, RpcError

WOUND_DOWN: int = -32010  # JSON-RPC's implementation-defined range; the API's code rides in the error's data
CAPABILITIES: dict[str, Any] = {"tools": {}, "resources": {}}
EMPTY: dict[str, dict[str, Any]] = {
    "ping": {},
    "tools/list": {"tools": []},
    "resources/list": {"resources": []},
    "resources/templates/list": {"resourceTemplates": []},
    "server/discover": {"supportedVersions": [MODERN, *LEGACY], "capabilities": CAPABILITIES, "instructions": RETIRED},
}


def result(call: Call, info: dict[str, str]) -> dict[str, Any]:
    if call.method == "initialize" and not call.modern:
        asked = call.params.get("protocolVersion")
        version = asked if asked in LEGACY else LEGACY[0]
        return {"protocolVersion": version, "capabilities": CAPABILITIES, "serverInfo": info, "instructions": RETIRED}
    if call.method in EMPTY:
        return EMPTY[call.method]
    raise RpcError(WOUND_DOWN, RETIRED, data={"code": WoundDown.code, "method": call.method})


def respond(body: bytes, headers: Headers, version: str) -> Response:
    """One request answered: read as ever (a malformed one is refused as ever), a notification taken, the rest above."""
    info = {"name": "glyphh", "title": "Glyphh", "version": version}
    try:
        call = protocol.read(body, headers)
    except RpcError as err:
        return JSONResponse(protocol.failure(err), err.status)
    if call.id is None:
        return Response(status_code=202)
    try:
        return JSONResponse(protocol.answer(call, result(call, info), info))
    except RpcError as err:
        err.id = call.id
        return JSONResponse(protocol.failure(err), err.status)
