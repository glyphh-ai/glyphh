"""The account panel: one MCP App resource (MCP Apps 2026-01-26), an HTML page that renders the account and acts by
calling the connector's own tools through the host. It inlines the MCP Apps client (@modelcontextprotocol/ext-apps
2.0.3, the bundle the glyphh mod's sign-in card ships). Its address carries its version: a new panel, a new address."""

from functools import lru_cache
from importlib import resources
from typing import Any

from glyphh_server.mcp.protocol import Call

URI: str = "ui://glyphh/account/4"
MIME: str = "text/html;profile=mcp-app"
EXTENSION: str = "io.modelcontextprotocol/ui"
RESOURCE: dict[str, str] = {
    "uri": URI,
    "name": "account",
    "title": "Glyphh account",
    "description": "Your Glyphh account: plan, each mod's limits and use, upgrade, billing, installs and grants.",
    "mimeType": MIME,
}


@lru_cache
def html() -> str:
    folder = resources.files("glyphh_server.mcp") / "panel"
    script = (folder / "mcp-app.js").read_text().replace("</script", "<\\/script")
    return (folder / "account.html").read_text().replace("__APP_JS__", script)


def contents() -> dict[str, Any]:
    return {"uri": URI, "mimeType": MIME, "text": html(), "_meta": {"ui": {"prefersBorder": True}}}


def shown(call: Call) -> bool:
    """Whether tools name the panel: a 2026-07-28 client only when it declares the extension and its mime type; on the
    earlier revisions a request carries no capabilities, so always (a client without panels ignores it)."""
    if call.capabilities is None:
        return True
    extensions = call.capabilities.get("extensions")
    ui = extensions.get(EXTENSION) if isinstance(extensions, dict) else None
    return isinstance(ui, dict) and MIME in (ui.get("mimeTypes") or [])
