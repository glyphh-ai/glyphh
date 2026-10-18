"""One JSON object per log line, each with its trace id, user and org, so any line leads to its request. No line
carries a caller's address for a path whose callers' addresses are never kept (a self-hosted runtime's heartbeat):
the access line uvicorn writes for it, the one line that would, is dropped."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from glyphh_server.obs import context

_HANDLER_NAME: str = "glyphh-json"
UNLOGGED_ADDRESS: frozenset[str] = frozenset({"/v1/license/verify"})


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        line: dict[str, Any] = {
            "at": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": context.trace_id.get(),
            "user_id": context.user_id.get(),
            "org_id": context.org_id.get(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            line.update(fields)
        if record.exc_info:
            line["error"] = self.formatException(record.exc_info)
        return json.dumps(line, default=str)


class NoAddress(logging.Filter):
    """uvicorn's access line is `client - "METHOD path HTTP/v" status`: dropped for those paths."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        path = str(args[2]).partition("?")[0] if isinstance(args, tuple) and len(args) > 2 else ""
        return path not in UNLOGGED_ADDRESS


def configure(level: str) -> None:
    """Send every log line to stdout as JSON. Safe to call again: the handler is replaced, never doubled."""
    access = logging.getLogger("uvicorn.access")
    for old in [f for f in access.filters if isinstance(f, NoAddress)]:
        access.removeFilter(old)
    access.addFilter(NoAddress())
    root = logging.getLogger()
    root.handlers = [h for h in root.handlers if h.get_name() != _HANDLER_NAME]
    handler = logging.StreamHandler(sys.stdout)
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level.upper())


def fields(**values: Any) -> dict[str, Any]:
    """Extra keys for one line: log.info("…", extra=fields(path=p))."""
    return {"fields": values}
