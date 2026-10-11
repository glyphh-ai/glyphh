"""Every MCP tool runs inside this guard: one log line per call with its trace id, a refusal reported
with its code, and a crash logged with its traceback and reported only as E_INTERNAL (failing closed)."""

import functools
import logging
import time
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from mcp.server.mcpserver.exceptions import ToolError

from glyphh_server.errors import INTERNAL_MESSAGE, GlyphhError
from glyphh_server.obs.context import current_trace_id
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.mcp")

P = ParamSpec("P")
R = TypeVar("R")


def guarded(name: str) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    def wrap(tool: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(tool)
        async def run(*args: P.args, **kwargs: P.kwargs) -> R:
            trace = current_trace_id()
            began = time.perf_counter()
            try:
                result = await tool(*args, **kwargs)
            except GlyphhError as err:
                log.info("tool refused", extra=fields(tool=name, code=err.code, reason=err.message))
                raise ToolError(f"{err.code}: {err.message} (trace {trace})") from err
            except Exception as err:
                log.exception("tool crashed", extra=fields(tool=name))
                raise ToolError(f"E_INTERNAL: {INTERNAL_MESSAGE} (trace {trace})") from err
            log.info("tool", extra=fields(tool=name, ms=round((time.perf_counter() - began) * 1000, 1)))
            return result

        return run

    return wrap
