"""The outermost layer of every request: its trace id, its log line, and the last line of defence.

A crash anywhere below is logged with its traceback and answered E_INTERNAL with the trace id, never with
the crash's own message (failing closed). The trace id is echoed as x-request-id on every response."""

import contextlib
import logging
import time

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from glyphh_server.api.errors import refusal
from glyphh_server.errors import INTERNAL_MESSAGE
from glyphh_server.obs.context import accept_trace_id, bound
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.request")

TRACE_HEADER: str = "x-request-id"


class TraceMiddleware:
    def __init__(self, app: ASGIApp, platform: str) -> None:
        self.app, self.platform = app, platform

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        trace = accept_trace_id(Headers(scope=scope).get(TRACE_HEADER))
        state = {"started": False, "status": 500}

        async def send_traced(message: Message) -> None:
            if message["type"] == "http.response.start":
                state["started"], state["status"] = True, message["status"]
                MutableHeaders(scope=message)[TRACE_HEADER] = trace
            await send(message)

        with bound(trace=trace):
            began = time.perf_counter()
            try:
                await self.app(scope, receive, send_traced)
            except Exception:
                log.exception("crashed", extra=fields(method=scope["method"], path=scope["path"]))
                if not state["started"]:
                    response = refusal(scope["path"], self.platform, "E_INTERNAL", INTERNAL_MESSAGE, 500)
                    await response(scope, receive, send_traced)
                else:
                    # The head is already sent: end the body where it stopped, so the connection closes cleanly.
                    with contextlib.suppress(Exception):
                        await send({"type": "http.response.body", "body": b"", "more_body": False})
            finally:
                ms = round((time.perf_counter() - began) * 1000, 1)
                log.info(
                    "request", extra=fields(method=scope["method"], path=scope["path"], status=state["status"], ms=ms)
                )
