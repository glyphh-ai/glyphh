"""What the connector answers, method by method. Stateless: every request stands alone, whichever revision it
speaks."""

from typing import Any

from glyphh_server.mcp import panel
from glyphh_server.mcp.protocol import INVALID_PARAMS, LEGACY, METHOD_NOT_FOUND, MODERN, Call, RpcError
from glyphh_server.mcp.tools import registry
from glyphh_server.mcp.tools.base import Context
from glyphh_server.ops.templates import installs

CAPABILITIES: dict[str, Any] = {"tools": {}, "resources": {}}
INSTRUCTIONS: str = (
    "Glyphh's account, from Claude: who you are (whoami), your plan (plan) and what you use of it (usage), what each "
    "plan costs and includes (plans), upgrading (upgrade) and billing (billing_portal), your installs, your org's "
    "members and invites, and the apps allowed to use this connector (connector_grants)."
)
# rrotor's: said only while GLYPHH_RROTOR is on, the default (its tools are offered only then too).
RROTOR_INSTRUCTIONS: str = (
    " Your self-hosted runtimes, their keys and offline licences. Your org's apps, what Claude made and published to "
    "its rrotors (apps, shown as cards with Open; a reviewer approves, rejects or retires one: app_approve, "
    "app_reject, app_retire). A rrotor is its own connector, at the mcp_url self_runtimes gives for it: its "
    "programs, CLIs, pipelines, its graph (the org's data as a knowledge graph with search: graph_schema, "
    "graph_search) and the form a person sets a pipeline's secrets in (secrets_form) are that connector's tools, "
    "never this one's. When the person asks for those and the rrotor's tools are not in the conversation, call "
    "self_runtimes and have them add its mcp_url to Claude as a connector."
)
ADA_INSTRUCTIONS: str = (
    " Ada Cloud, decisions from your own precedents: make a model from a JSON spec (ada_model_create), load its "
    "history (ada_record_many, or ada_import with an upload link), learn (ada_learn), ask (ada_decide, ada_query, "
    "ada_probabilities, ada_facts), chain models (ada_beam), tune one lever at a time with a backtest first "
    "(ada_backtest, ada_settings, ada_versions, ada_activate), follow jobs (ada_job), export (ada_export), and make "
    "API keys for your code (create_api_key). Reads count against your plan's month (usage). The template library ("
    "templates, "
    "template_install): bundles you install for yourself, each adding tools of your own, such as Agentic memory, your "
    "glyphh."
)


def server_info(ctx: Context) -> dict[str, str]:
    return {"name": "glyphh", "title": "Glyphh", "version": ctx.settings.version}


async def instructions(ctx: Context) -> str:
    """What the server is for, and while Ada Cloud is on, how to use each template the person has installed."""
    said = INSTRUCTIONS + (RROTOR_INSTRUCTIONS if ctx.settings.rrotor else "")
    if ctx.ada is None:
        return said
    return " ".join([said + ADA_INSTRUCTIONS, *(b.instructions for b in await installs.installed(ctx.conn, ctx.who))])


async def initialize(ctx: Context, call: Call) -> dict[str, Any]:
    if call.modern:
        raise RpcError(METHOD_NOT_FOUND, "initialize is not part of MCP 2026-07-28: use server/discover.", 404)
    asked = call.params.get("protocolVersion")
    return {
        "protocolVersion": asked if asked in LEGACY else LEGACY[0],
        "capabilities": CAPABILITIES,
        "serverInfo": server_info(ctx),
        "instructions": await instructions(ctx),
    }


async def discover(ctx: Context) -> dict[str, Any]:
    said = await instructions(ctx)
    return {"supportedVersions": [MODERN, *LEGACY], "capabilities": CAPABILITIES, "instructions": said}


def read_resource(call: Call) -> dict[str, Any]:
    uri = call.params.get("uri")
    if uri not in panel.PAGES:
        raise RpcError(INVALID_PARAMS, f"There is no resource {uri!r}.", data={"uri": uri})
    return {"contents": [panel.contents(uri)]}


async def handle(ctx: Context, call: Call) -> dict[str, Any]:
    match call.method:
        case "initialize":
            return await initialize(ctx, call)
        case "ping":
            return {}
        case "server/discover":
            return await discover(ctx)
        case "tools/list":
            return {"tools": [registry.listed(t, panel.shown(call)) for t in (await registry.listing(ctx)).values()]}
        case "tools/call":
            return await registry.call(ctx, call.params)
        case "resources/list":
            # The apps panel only while rrotor is shown (GLYPHH_RROTOR), the decision card while Ada Cloud is on.
            hidden = set() if ctx.settings.rrotor else {panel.APPS_URI}
            hidden |= {panel.DECISION_URI} if ctx.ada is None else set()
            return {"resources": [r for r in panel.RESOURCES if r["uri"] not in hidden]}
        case "resources/templates/list":
            return {"resourceTemplates": []}
        case "resources/read":
            return read_resource(call)
    raise RpcError(METHOD_NOT_FOUND, f"There is no method {call.method!r}.", 404 if call.modern else 200)
