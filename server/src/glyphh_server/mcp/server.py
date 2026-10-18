"""What the connector answers, method by method. Stateless: every request stands alone, whichever revision it
speaks."""

from typing import Any

from glyphh_server.mcp import panel
from glyphh_server.mcp.protocol import INVALID_PARAMS, LEGACY, METHOD_NOT_FOUND, MODERN, Call, RpcError
from glyphh_server.mcp.tools import registry
from glyphh_server.mcp.tools.base import Context

CAPABILITIES: dict[str, Any] = {"tools": {}, "resources": {}}
INSTRUCTIONS: str = (
    "Glyphh's account, from Claude: who you are (whoami), your plan (plan), what each plan costs and includes (plans), "
    "upgrading (upgrade) and billing (billing_portal), your installs, your org's members and invites, your runtimes, "
    "and the apps allowed to use this connector (connector_grants)."
)


def server_info(ctx: Context) -> dict[str, str]:
    return {"name": "glyphh", "title": "Glyphh", "version": ctx.settings.version}


def initialize(ctx: Context, call: Call) -> dict[str, Any]:
    if call.modern:
        raise RpcError(METHOD_NOT_FOUND, "initialize is not part of MCP 2026-07-28: use server/discover.", 404)
    asked = call.params.get("protocolVersion")
    return {
        "protocolVersion": asked if asked in LEGACY else LEGACY[0],
        "capabilities": CAPABILITIES,
        "serverInfo": server_info(ctx),
        "instructions": INSTRUCTIONS,
    }


def discover() -> dict[str, Any]:
    return {"supportedVersions": [MODERN, *LEGACY], "capabilities": CAPABILITIES, "instructions": INSTRUCTIONS}


def read_resource(call: Call) -> dict[str, Any]:
    if call.params.get("uri") != panel.URI:
        raise RpcError(
            INVALID_PARAMS, f"There is no resource {call.params.get('uri')!r}.", data={"uri": call.params.get("uri")}
        )
    return {"contents": [panel.contents()]}


async def handle(ctx: Context, call: Call) -> dict[str, Any]:
    match call.method:
        case "initialize":
            return initialize(ctx, call)
        case "ping":
            return {}
        case "server/discover":
            return discover()
        case "tools/list":
            return {"tools": [registry.listed(t, panel.shown(call)) for t in registry.TOOLS.values()]}
        case "tools/call":
            return await registry.call(ctx, call.params)
        case "resources/list":
            return {"resources": [panel.RESOURCE]}
        case "resources/templates/list":
            return {"resourceTemplates": []}
        case "resources/read":
            return read_resource(call)
    raise RpcError(METHOD_NOT_FOUND, f"There is no method {call.method!r}.", 404 if call.modern else 200)
