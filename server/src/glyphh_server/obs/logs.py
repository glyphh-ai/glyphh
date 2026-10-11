"""One JSON object per log line, each with its trace id, user and org, so any line leads to its request."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from glyphh_server.obs import context

_HANDLER_NAME: str = "glyphh-json"


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


def configure(level: str) -> None:
    """Send every log line to stdout as JSON. Safe to call again: the handler is replaced, never doubled."""
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
