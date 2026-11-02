"""What the connector answers, method by method. Stateless: every request stands alone, whichever revision it
speaks."""

from typing import Any

from glyphh_server.mcp import panel
from glyphh_server.mcp.protocol import INVALID_PARAMS, LEGACY, METHOD_NOT_FOUND, MODERN, Call, RpcError
from glyphh_server.mcp.tools import registry
from glyphh_server.mcp.tools.base import Context

CAPABILITIES: dict[str, Any] = {"tools": {}, "resources": {}}
INSTRUCTIONS: str = (
    "Glyphh's account, from Claude: who you are (whoami), your plan (plan) and what you use of it (usage), what each "
    "plan costs and includes (plans), upgrading (upgrade) and billing (billing_portal), your installs, your org's "
    "members and invites, your self-hosted runtimes, their keys and offline licences, and the apps allowed to use "
    "this connector (connector_grants). Your org's apps, what Claude made and published to its rrotors (apps, shown "
    "as cards with Open; a reviewer approves, rejects or retires one: app_approve, app_reject, app_retire)."
)
ADA_INSTRUCTIONS: str = (
    " Ada Cloud, decisions from your own precedents: make a model from a JSON spec (ada_model_create), load its "
    "history (ada_record_many, or ada_import with an upload link), learn (ada_learn), ask (ada_decide, ada_query, "
    "ada_probabilities, ada_facts), tune one lever at a time with a backtest first (ada_backtest, ada_settings, "
    "ada_versions, ada_activate), follow jobs (ada_job), export (ada_export), and make API keys for your code "
    "(create_api_key). Reads count against your plan's month (usage)."
)


def server_info(ctx: Context) -> dict[str, str]:
    return {"name": "glyphh", "title": "Glyphh", "version": ctx.settings.version}


def instructions(ctx: Context) -> str:
    return INSTRUCTIONS + (ADA_INSTRUCTIONS if ctx.ada is not None else "")


def initialize(ctx: Context, call: Call) -> dict[str, Any]:
    if call.modern:
        raise RpcError(METHOD_NOT_FOUND, "initialize is not part of MCP 2026-07-28: use server/discover.", 404)
    asked = call.params.get("protocolVersion")
    return {
        "protocolVersion": asked if asked in LEGACY else LEGACY[0],
        "capabilities": CAPABILITIES,
        "serverInfo": server_info(ctx),
        "instructions": instructions(ctx),
    }


def discover(ctx: Context) -> dict[str, Any]:
    return {"supportedVersions": [MODERN, *LEGACY], "capabilities": CAPABILITIES, "instructions": instructions(ctx)}


def read_resource(call: Call) -> dict[str, Any]:
    uri = call.params.get("uri")
    if uri not in panel.PAGES:
        raise RpcError(INVALID_PARAMS, f"There is no resource {uri!r}.", data={"uri": uri})
    return {"contents": [panel.contents(uri)]}


async def handle(ctx: Context, call: Call) -> dict[str, Any]:
    match call.method:
        case "initialize":
            return initialize(ctx, call)
        case "ping":
            return {}
        case "server/discover":
            return discover(ctx)
        case "tools/list":
            return {"tools": [registry.listed(t, panel.shown(call)) for t in registry.available(ctx).values()]}
        case "tools/call":
            return await registry.call(ctx, call.params)
        case "resources/list":
            return {"resources": list(panel.RESOURCES)}
        case "resources/templates/list":
            return {"resourceTemplates": []}
        case "resources/read":
            return read_resource(call)
    raise RpcError(METHOD_NOT_FOUND, f"There is no method {call.method!r}.", 404 if call.modern else 200)
