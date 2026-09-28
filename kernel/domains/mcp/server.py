"""
MCP Server — the glyphh runtime's control plane.

One self-describing surface: decisions (decide / record_decision), the
model lifecycle (list / deploy / seed / unload / delete), and whatever
tools the deployed models themselves export. Every answer is structured
— fact trees, never prose. There is no chat: capabilities belong to
models, and the runtime just hosts and surfaces them.

Metering counts every model-tool and decision call, best-effort.
"""

import json
import logging
from typing import Any

from mcp.server.lowlevel.server import Server
from mcp.types import (
    CallToolResult,
    TextContent,
    Tool,
)

from domains.auth.service import AuthService

logger = logging.getLogger(__name__)


def _meter(op: str) -> None:
    """Best-effort metering of MCP operations."""
    try:
        from glyphh.licensing import get_current_license
        from glyphh.metering import get_meter

        meter = get_meter()
        count = meter.record(op)
        license_info = get_current_license()
        if not license_info.is_unlimited:
            limit = license_info.max_encodings_per_month
            threshold = license_info.encoding_warning_threshold()
            if count >= limit:
                logger.warning(
                    f"Monthly operation limit exceeded "
                    f"({count:,}/{limit:,}). Tier: {license_info.tier}")
            elif threshold and count >= threshold:
                logger.warning(
                    f"Approaching monthly limit "
                    f"({count:,}/{limit:,}, {count/limit*100:.0f}%)")
    except Exception:
        pass


def create_mcp_server(
    auth_service: AuthService,
    model_manager: Any = None,
) -> Server:
    """Create the MCP server: decisions + model lifecycle + model tools.

    Args:
        auth_service: AuthService for token validation
        model_manager: ModelManager for the admin tools and for surfacing
            model-exported tools; omitted -> decisions only
    """
    from domains.mcp.admin_tools import (
        ADMIN_TOOL_NAMES,
        admin_tool_definitions,
        handle_admin_tool,
    )
    from domains.mcp.decision_tools import (
        DECISION_TOOL_NAMES,
        decision_tool_definitions,
        handle_decision_tool,
    )

    app = Server("glyphh")

    @app.list_tools()
    async def list_tools() -> list[Tool]:
        tools = list(decision_tool_definitions())
        if model_manager is not None:
            tools.extend(admin_tool_definitions())
            # Deployed models expose their own tools (MCP_TOOLS +
            # handle_mcp_tool in the model's encoder.py). Capabilities
            # belong to models; the runtime just surfaces them.
            builtin = {t.name for t in tools}
            for model in model_manager.list_models():
                for spec in getattr(model, "mcp_tools", []) or []:
                    name = spec.get("name")
                    if not name or name in builtin:
                        continue
                    tools.append(Tool(
                        name=name,
                        description=spec.get("description", ""),
                        inputSchema=spec.get("input_schema")
                        or spec.get("inputSchema")
                        or {"type": "object", "properties": {}},
                    ))
                    builtin.add(name)
        return tools

    def _ok(payload: dict) -> CallToolResult:
        return CallToolResult(content=[TextContent(
            type="text", text=json.dumps(payload, ensure_ascii=False),
        )])

    def _err(msg: str) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": msg}))],
            isError=True,
        )

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> CallToolResult:
        args = arguments or {}

        if name in ADMIN_TOOL_NAMES:
            try:
                return _ok(await handle_admin_tool(model_manager, name, args))
            except ValueError as e:
                return _err(str(e))
            except Exception as e:
                logger.error(f"{name}() failed: {e}", exc_info=True)
                return _err(str(e))

        if name in DECISION_TOOL_NAMES:
            _meter("decide")
            try:
                return _ok(await handle_decision_tool(name, args))
            except ValueError as e:
                return _err(str(e))
            except Exception as e:
                logger.error(f"{name}() failed: {e}", exc_info=True)
                return _err(str(e))

        # Model-exported tools: dispatch to the owning model's handler
        if model_manager is not None:
            for model in model_manager.list_models():
                specs = getattr(model, "mcp_tools", []) or []
                if any(spec.get("name") == name for spec in specs):
                    handler = getattr(model, "handle_mcp_tool_fn", None)
                    if handler is None:
                        return _err(f"Model {model.model_id} exports "
                                    f"{name} but has no handler")
                    _meter(model.model_id)
                    try:
                        result = await handler(name, args, {
                            "model_manager": model_manager,
                            "model_id": model.model_id,
                            "org_id": model.org_id,
                        })
                        return _ok(result if isinstance(result, dict)
                                   else {"result": result})
                    except Exception as e:
                        logger.error(f"{name}() failed: {e}", exc_info=True)
                        return _err(str(e))

        return _err(f"Unknown tool: {name}")

    return app
