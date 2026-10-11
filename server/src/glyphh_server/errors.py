"""Every failure the server means to report, each with a stable code a caller can branch on.

Anything that is not a GlyphhError is a crash: it is logged with its traceback and its trace id, and the
caller sees only E_INTERNAL and the trace id, never the crash's own message. That is failing closed."""

from typing import Any, ClassVar


class GlyphhError(Exception):
    code: ClassVar[str] = "E_INTERNAL"
    status: ClassVar[int] = 500

    def __init__(self, message: str, **detail: Any) -> None:
        super().__init__(message)
        self.message: str = message
        self.detail: dict[str, Any] = detail


class Invalid(GlyphhError):
    code = "E_INVALID"
    status = 422


class Unauthorized(GlyphhError):
    code = "E_UNAUTHORIZED"
    status = 401


class Forbidden(GlyphhError):
    code = "E_FORBIDDEN"
    status = 403


class NotFound(GlyphhError):
    code = "E_NOT_FOUND"
    status = 404


class Conflict(GlyphhError):
    code = "E_CONFLICT"
    status = 409


class LimitReached(GlyphhError):
    """The org's plan does not allow more: seats, machines, credits. Upgrade, or free one up."""

    code = "E_LIMIT"
    status = 403


class Unavailable(GlyphhError):
    code = "E_UNAVAILABLE"
    status = 503


INTERNAL_MESSAGE: str = "Something went wrong on our side. Quote the trace id to support."
