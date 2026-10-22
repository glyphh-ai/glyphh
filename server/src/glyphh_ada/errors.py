"""Ada Cloud's refusals. The API raises them as the server's own (one shape: {"error": {"code", "message",
"trace_id", ...}}); a worker raises Refusal, which travels back on the reply list and is raised again by the API with
the worker's code and status. The codes a caller of rrotor knows are kept (E_AUTH, E_MODEL_MISSING), so SDK 3.0 reads
the cloud's refusals as it reads a runtime's."""

from typing import Any

from glyphh_server.errors import GlyphhError


class Refusal(Exception):
    """A worker's refusal: code, message, HTTP status and detail, sent back to the API as they are."""

    def __init__(self, code: str, message: str, status: int = 422, **detail: Any) -> None:
        super().__init__(message)
        self.code, self.message, self.status, self.detail = code, message, status, detail


class Refused(GlyphhError):
    """A worker's refusal raised in the API, with the worker's own code and status."""

    def __init__(self, code: str, message: str, status: int, **detail: Any) -> None:
        super().__init__(message, **detail)
        self.code = code  # type: ignore[misc]
        self.status = status  # type: ignore[misc]


class NoKey(GlyphhError):
    code = "E_AUTH"
    status = 401


class SignInOnly(GlyphhError):
    code = "E_FORBIDDEN"
    status = 403


class ModelMissing(GlyphhError):
    code = "E_MODEL_MISSING"
    status = 404


class BadRequest(GlyphhError):
    code = "E_INVALID"
    status = 400


class Timeout(GlyphhError):
    code = "E_TIMEOUT"
    status = 504


class RateLimited(GlyphhError):
    """More calls a second than the org's plan allows: again after `retry_after` seconds (also its header)."""

    code = "E_RATE"
    status = 429

    def __init__(self, message: str, retry_after: int, **detail: Any) -> None:
        super().__init__(message, retry_after=retry_after, **detail)
        self.headers = {"retry-after": str(retry_after)}


def model_missing(name: str) -> Refusal:
    return Refusal("E_MODEL_MISSING", f"No model named {name} in this org.", 404, model=name)
