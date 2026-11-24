"""The panels: MCP App resources (MCP Apps 2026-01-26), each an HTML page that renders what its tools answer and acts
by calling the connector's own tools through the host. The account panel (`ui://glyphh/account/5`) and the decision
card (`ui://glyphh/decision/1`: one Ada decision, from ada_decide, with its probabilities, whether Ada asks first and
the precedents it stands on; Approve or a correction records the case through the tool its answer's `teach` names).
Each inlines the MCP Apps client (@modelcontextprotocol/ext-apps 2.0.3, the bundle the glyphh plugin's sign-in card
ships). An address carries its version: a new panel, a new address."""

from functools import lru_cache
from importlib import resources
from typing import Any

from glyphh_server.mcp.protocol import Call

URI: str = "ui://glyphh/account/5"
DECISION_URI: str = "ui://glyphh/decision/1"
MIME: str = "text/html;profile=mcp-app"
EXTENSION: str = "io.modelcontextprotocol/ui"
RESOURCE: dict[str, str] = {
    "uri": URI,
    "name": "account",
    "title": "Glyphh account",
    "description": "Your Glyphh account: plan, what it includes and its use, upgrade, billing, installs and grants.",
    "mimeType": MIME,
}
DECISION_RESOURCE: dict[str, str] = {
    "uri": DECISION_URI,
    "name": "decision",
    "title": "Ada decision",
    "description": "One Ada decision: the outcome, its probabilities, whether Ada asks you first and the precedents it "
    "stands on; approve it or correct it, and the case is recorded as a precedent the model learns from.",
    "mimeType": MIME,
}
RESOURCES: tuple[dict[str, str], ...] = (RESOURCE, DECISION_RESOURCE)
PAGES: dict[str, str] = {URI: "account.html", DECISION_URI: "decision.html"}


@lru_cache
def html(uri: str = URI) -> str:
    folder = resources.files("glyphh_server.mcp") / "panel"
    script = (folder / "mcp-app.js").read_text().replace("</script", "<\\/script")
    return (folder / PAGES[uri]).read_text().replace("__APP_JS__", script)


def contents(uri: str = URI) -> dict[str, Any]:
    return {"uri": uri, "mimeType": MIME, "text": html(uri), "_meta": {"ui": {"prefersBorder": True}}}


def shown(call: Call) -> bool:
    """Whether tools name the panel: a 2026-07-28 client only when it declares the extension and its mime type; on the
    earlier revisions a request carries no capabilities, so always (a client without panels ignores it)."""
    if call.capabilities is None:
        return True
    extensions = call.capabilities.get("extensions")
    ui = extensions.get(EXTENSION) if isinstance(extensions, dict) else None
    return isinstance(ui, dict) and MIME in (ui.get("mimeTypes") or [])
