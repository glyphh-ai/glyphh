"""Who and what a log line is about, carried through a request without passing it by hand."""

import re
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
user_id: ContextVar[str | None] = ContextVar("user_id", default=None)
org_id: ContextVar[str | None] = ContextVar("org_id", default=None)

_TRACE_SHAPE: re.Pattern[str] = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def new_trace_id() -> str:
    return uuid.uuid4().hex


def accept_trace_id(given: str | None) -> str:
    """A caller's own id when it is a safe shape (so a client can follow its call), else a new one."""
    return given if given and _TRACE_SHAPE.match(given) else new_trace_id()


def current_trace_id() -> str:
    """The trace id in force, making one if none is set, so no error is ever reported without one."""
    found = trace_id.get()
    if found is None:
        found = new_trace_id()
        trace_id.set(found)
    return found


@contextmanager
def bound(*, trace: str | None = None, user: str | None = None, org: str | None = None) -> Iterator[None]:
    """Set the trace id, user and org for the block, and put back what was there after."""
    tokens = []
    if trace is not None:
        tokens.append((trace_id, trace_id.set(trace)))
    if user is not None:
        tokens.append((user_id, user_id.set(user)))
    if org is not None:
        tokens.append((org_id, org_id.set(org)))
    try:
        yield
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
