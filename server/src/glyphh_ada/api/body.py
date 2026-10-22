"""A request's body within its bound before anything parses it: 1 MB, record_many 5 MB (413 E_TOO_LARGE)."""

from fastapi import Request

from glyphh_ada import limits
from glyphh_server.errors import TooLarge


async def bounded(request: Request) -> None:
    most = limits.RECORD_MANY_BODY_MAX if request.url.path.endswith("/record_many") else limits.BODY_MAX
    declared = request.headers.get("content-length", "")
    if (declared.isdigit() and int(declared) > most) or len(await request.body()) > most:
        raise TooLarge(f"A request's body is at most {most} bytes here.", max=most)
