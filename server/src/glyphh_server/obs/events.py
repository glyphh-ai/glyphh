"""The server's own errors and warnings, kept for its staff as ops events (ops_events, admin view): every warning or
worse a `glyphh.*` logger writes, in the API (a crash, a 5xx, a Stripe webhook that failed) and in the Ada workers (a
worker's failure or death, a job's), and the minute tick's (a part that failed). A logging handler puts each on a
Redis list as it is logged, a few hundred bytes, only on a warning or worse, never on the request's way; the tick
moves the list to Postgres (obs/events_store.py). A Redis that is down loses the event, never the request: the
handler swallows its own failures and never logs them."""

import json
import logging
import threading
import traceback
from typing import Any

from redis import Redis

from glyphh_server.obs import context

QUEUE: str = "ops:events:in"
KEPT: int = 10_000  # the list is cut to this many: a flood of one error can't fill Redis
HANDLER_NAME: str = "glyphh-ops"
TIMEOUT: float = 0.25
# Warnings that are no fault: a worker group idling while Ada Cloud is off, the schema step's own notes.
QUIET: frozenset[str] = frozenset(
    {
        "Ada Cloud is off (GLYPHH_ADA_CLOUD): this worker group does nothing",
        "migrated: %s",
        "database kept: GLYPHH_RESET_DATABASE is not set",
    }
)
KINDS: dict[str, str] = {
    "glyphh.request": "crash",
    "glyphh.api": "http",
    "glyphh.ada": "worker",
    "glyphh.billing": "stripe",
    "glyphh.staff": "staff",
}


def severity(level: int) -> str:
    return "critical" if level >= logging.CRITICAL else "error" if level >= logging.ERROR else "warning"


def kind_of(record: logging.LogRecord, about: dict[str, Any]) -> str:
    """What an event is about: a job, Stripe, the tick, a worker, a crash, an HTTP refusal; else its logger's name."""
    if record.name == "glyphh.ada" and str(record.msg).startswith("job"):
        return "job"
    if str(about.get("path", "")).startswith("/v1/stripe"):
        return "stripe"
    if record.name == "glyphh.runtime":
        return "tick" if str(record.msg).startswith("tick") else "runtime"
    return KINDS.get(record.name, record.name.removeprefix("glyphh."))


def _crash(record: logging.LogRecord) -> str | None:
    """The exception, as its traceback's last lines: never its frames' values."""
    if not record.exc_info or record.exc_info[0] is None:
        return None
    return "".join(traceback.format_exception(*record.exc_info))[-2000:]


def event(record: logging.LogRecord) -> dict[str, Any]:
    about = getattr(record, "fields", None)
    about = dict(about) if isinstance(about, dict) else {}
    crash = _crash(record)
    if crash:
        about["error"] = crash
    return {
        "at": record.created,
        "severity": severity(record.levelno),
        "kind": kind_of(record, about),
        "source": record.name,
        "message": record.getMessage()[:500],
        "detail": about,
        "org": context.org_id.get() or about.get("org"),
        "trace": context.trace_id.get(),
    }


class OpsHandler(logging.Handler):
    def __init__(self, redis_url: str) -> None:
        super().__init__(level=logging.WARNING)
        self.set_name(HANDLER_NAME)
        self.redis = Redis.from_url(redis_url, socket_timeout=TIMEOUT, socket_connect_timeout=TIMEOUT)
        self.local = threading.local()

    def emit(self, record: logging.LogRecord) -> None:
        mine = record.name.startswith("glyphh.") and record.levelno >= self.level and str(record.msg) not in QUIET
        if not mine or getattr(self.local, "busy", False):
            return
        self.local.busy = True  # anything Redis's client logs while this runs is not sent again
        try:
            line = json.dumps(event(record), default=str)
            self.redis.pipeline(transaction=False).rpush(QUEUE, line).ltrim(QUEUE, -KEPT, -1).execute()
        except Exception:  # noqa: BLE001  # an event lost, never the request or the log line
            pass
        finally:
            self.local.busy = False


def install(redis_url: str) -> OpsHandler:
    """The handler on the root logger, replacing one put there before (safe to call again)."""
    root = logging.getLogger()
    for old in [h for h in root.handlers if h.get_name() == HANDLER_NAME]:
        root.removeHandler(old)
    handler = OpsHandler(redis_url)
    root.addHandler(handler)
    return handler
