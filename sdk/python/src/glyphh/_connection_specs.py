"""My connections, as calls: the services to connect, connecting through Pipedream's own page (open the answer's
`url`, then `check_connection`), reconnecting, disconnecting, and each tool's Allow, Ask or Deny."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from glyphh._calls import plain_call as _call
from glyphh._gen.api.connections import (
    check_connection,
    connect,
    disconnect,
    list_connections,
    list_services,
    list_tools,
    reconnect,
    set_tools,
)
from glyphh._gen.models.service_in import ServiceIn
from glyphh._gen.models.tool_changes import ToolChanges
from glyphh._gen.types import UNSET

Spec = tuple[Any, dict[str, Any]]


def _id(power_id: str) -> dict[str, Any]:
    return {"power_id": UUID(power_id)}


CONNECTION_SPECS: dict[str, Callable[..., Spec]] = {
    "services": lambda q="", after=None, limit=25: (
        _call(list_services),
        {"q": q, "after": after or UNSET, "limit": limit},
    ),
    "connections": lambda: (_call(list_connections), {}),
    "connect": lambda service: (_call(connect), {"body": ServiceIn(service=service)}),
    "reconnect": lambda power_id: (_call(reconnect), _id(power_id)),
    "check_connection": lambda power_id: (_call(check_connection), _id(power_id)),
    "disconnect": lambda power_id: (_call(disconnect), _id(power_id)),
    "tools": lambda power_id, q="", page=1, size=50: (
        _call(list_tools),
        {**_id(power_id), "q": q, "page": page, "size": size},
    ),
    "set_tools": lambda power_id, changes: (
        _call(set_tools),
        {**_id(power_id), "body": ToolChanges.from_dict({"changes": changes})},
    ),
}
