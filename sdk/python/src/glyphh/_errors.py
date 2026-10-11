import json

import httpx


class GlyphhError(Exception):
    """A request the server refused or failed: its HTTP status (0 when the server was never reached), its body,
    and, when the server sent one, its error code and trace id (quote the trace id to find the request)."""

    def __init__(self, status: int, body: object) -> None:
        detail = body.get("error") if isinstance(body, dict) else None
        detail = detail if isinstance(detail, dict) else {}
        super().__init__(detail.get("message") or f"Glyphh request failed with status {status}")
        self.status = status
        self.body = body
        self.code: str | None = detail.get("code")
        self.trace_id: str | None = detail.get("trace_id")


def body_of(content: bytes) -> object:
    try:
        return json.loads(content)
    except ValueError:
        return content.decode(errors="replace")


def refused(status: int, content: bytes) -> GlyphhError:
    return GlyphhError(status, body_of(content))


def unreachable(error: httpx.TransportError) -> GlyphhError:
    return GlyphhError(0, str(error))
